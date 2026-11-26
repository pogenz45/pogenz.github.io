from __future__ import annotations

import mimetypes
from pathlib import Path
from typing import Any

import httpx

from src.adapters.base import BasePublisherAdapter, PublishError, to_aware_datetime
from src.config import AppSettings
from src.models import JobStatus, Platform, Provider, PublishResult, ResolvedTargetPayload


def _guess_video_mime(video_path: Path) -> str:
    mime, _ = mimetypes.guess_type(str(video_path))
    if mime and mime.startswith("video/"):
        return mime
    ext = video_path.suffix.lower()
    if ext == ".mov":
        return "video/quicktime"
    if ext == ".webm":
        return "video/webm"
    return "video/mp4"


class ZernioTikTokAdapter(BasePublisherAdapter):
    """
    Adapter đăng video TikTok qua Zernio API (trước đây là Late / getlate.dev).
    - Miễn phí $0/tháng cho 2 tài khoản đầu tiên (vừa khít 2 kênh TikTok!)
    - Hỗ trợ presigned upload trực tiếp lên storage của Zernio (không cần tự thuê S3/R2)
    - Hỗ trợ hẹn giờ (scheduledFor + timezone)
    """

    def __init__(
        self,
        settings: AppSettings,
        *,
        http_client: httpx.Client | None = None,
    ) -> None:
        self.settings = settings
        self._external_client = http_client

    def _client(self) -> httpx.Client:
        if self._external_client is not None:
            return self._external_client
        return httpx.Client(timeout=httpx.Timeout(connect=30.0, read=180.0, write=300.0, pool=30.0))

    def _auth_headers(self) -> dict[str, str]:
        if not self.settings.zernio_api_key:
            raise PublishError(
                "Thiếu `ZERNIO_API_KEY` trong file `.env`. Hãy lấy API key từ dashboard Zernio.",
                retryable=False,
            )
        return {
            "Authorization": f"Bearer {self.settings.zernio_api_key}",
            "Content-Type": "application/json",
        }

    def _handle_error_response(self, resp: httpx.Response, step: str) -> None:
        if 200 <= resp.status_code < 300:
            return
        try:
            body = resp.json()
        except Exception:
            body = {"raw_text": resp.text[:1000]}
        retryable = resp.status_code in (429, 500, 502, 503, 504)
        raise PublishError(
            f"Zernio API lỗi ở bước {step} (HTTP {resp.status_code}): {body}",
            retryable=retryable,
            status_code=resp.status_code,
            raw_response=body if isinstance(body, dict) else None,
        )

    def list_accounts(self) -> list[dict[str, Any]]:
        """Lấy danh sách tài khoản đã kết nối OAuth trên Zernio để lấy `accountId`."""
        url = f"{self.settings.zernio_base_url}/accounts"
        client = self._client()
        should_close = self._external_client is None
        try:
            resp = client.get(url, headers=self._auth_headers())
            self._handle_error_response(resp, "list_accounts")
            data = resp.json()
            if isinstance(data, list):
                return data
            if isinstance(data, dict):
                return data.get("accounts") or data.get("data") or []
            return []
        finally:
            if should_close:
                client.close()

    def upload_media_presigned(self, video_path: Path) -> str:
        """
        Bước 1: POST /media/presign -> nhận uploadUrl + publicUrl
        Bước 2: PUT uploadUrl với raw file binary (KHÔNG gửi Authorization header)
        """
        if not video_path.exists():
            raise PublishError(f"Không tìm thấy file video: {video_path}", retryable=False)

        content_type = _guess_video_mime(video_path)
        file_size = video_path.stat().st_size

        client = self._client()
        should_close = self._external_client is None
        try:
            presign_url = f"{self.settings.zernio_base_url}/media/presign"
            presign_payload = {
                "filename": video_path.name,
                "contentType": content_type,
                "size": file_size,
            }
            resp = client.post(presign_url, headers=self._auth_headers(), json=presign_payload)
            self._handle_error_response(resp, "media/presign")
            data = resp.json()

            upload_url = data.get("uploadUrl")
            public_url = data.get("publicUrl")
            if not upload_url or not public_url:
                raise PublishError(
                    f"Zernio /media/presign không trả về đủ uploadUrl/publicUrl: {data}",
                    retryable=False,
                    raw_response=data,
                )

            def _file_chunks():
                with video_path.open("rb") as fh:
                    while True:
                        chunk = fh.read(4 * 1024 * 1024)
                        if not chunk:
                            break
                        yield chunk

            put_headers = {
                "Content-Type": content_type,
                "Content-Length": str(file_size),
            }
            put_resp = client.put(upload_url, headers=put_headers, content=_file_chunks())
            self._handle_error_response(put_resp, "media/put_binary")
            return str(public_url)
        except httpx.HTTPError as exc:
            raise PublishError(f"Lỗi mạng khi upload media lên Zernio: {exc}", retryable=True) from exc
        finally:
            if should_close:
                client.close()

    def build_post_body(self, payload: ResolvedTargetPayload, media_url: str) -> dict[str, Any]:
        account_id = payload.channel.account_id
        if not account_id or account_id.startswith("REPLACE_WITH_"):
            raise PublishError(
                f"Kênh '{payload.channel.key}' chưa được cấu hình `account_id` Zernio hợp lệ. "
                "Hãy chạy `python -m src.cli check-zernio` để lấy accountId.",
                retryable=False,
            )

        tiktok_settings: dict[str, Any] = {
            "privacy_level": payload.privacy or "PUBLIC_TO_EVERYONE",
            "allow_comment": bool(payload.extra.get("allow_comment", True)),
            "allow_duet": bool(payload.extra.get("allow_duet", True)),
            "allow_stitch": bool(payload.extra.get("allow_stitch", True)),
            "content_preview_confirmed": True,
            "express_consent_given": True,
        }
        if payload.is_ai_generated:
            tiktok_settings["is_aigc"] = True

        body: dict[str, Any] = {
            "content": payload.caption[:2200],
            "mediaItems": [{"type": "video", "url": media_url}],
            "platforms": [{"platform": "tiktok", "accountId": account_id}],
            "tiktokSettings": tiktok_settings,
        }

        if payload.scheduled_at is not None:
            aware_local = to_aware_datetime(payload.scheduled_at, payload.timezone)
            body["scheduledFor"] = aware_local.strftime("%Y-%m-%dT%H:%M:%S")
            body["timezone"] = payload.timezone
        else:
            body["publishNow"] = True

        return body

    def build_request_preview(self, payload: ResolvedTargetPayload) -> dict[str, Any]:
        media_url = payload.public_video_url or f"<PRESIGN_UPLOAD:{payload.video_path.name}>"
        account_id = payload.channel.account_id or "<MISSING_ACCOUNT_ID>"
        preview_payload = payload.model_copy(
            update={"channel": payload.channel.model_copy(update={"account_id": account_id})}
        )
        # Tránh ném lỗi khi dry-run chỉ để xem khung request nếu user chưa điền account_id
        if account_id.startswith("REPLACE_WITH_") or account_id == "<MISSING_ACCOUNT_ID>":
            body: dict[str, Any] = {
                "note": "Cần thay `account_id` thật trong config/channels.json trước khi đăng thật",
                "content": payload.caption[:2200],
                "mediaItems": [{"type": "video", "url": media_url}],
                "platforms": [{"platform": "tiktok", "accountId": account_id}],
            }
            if payload.scheduled_at is not None:
                aware_local = to_aware_datetime(payload.scheduled_at, payload.timezone)
                body["scheduledFor"] = aware_local.strftime("%Y-%m-%dT%H:%M:%S")
                body["timezone"] = payload.timezone
            else:
                body["publishNow"] = True
        else:
            body = self.build_post_body(preview_payload, media_url)

        return {
            "endpoint": f"POST {self.settings.zernio_base_url}/posts",
            "needs_presign_upload": payload.public_video_url is None,
            "body": body,
        }

    def publish(self, payload: ResolvedTargetPayload, idempotency_key: str) -> PublishResult:
        media_url = payload.public_video_url or self.upload_media_presigned(payload.video_path)
        body = self.build_post_body(payload, media_url)

        client = self._client()
        should_close = self._external_client is None
        try:
            resp = client.post(
                f"{self.settings.zernio_base_url}/posts",
                headers=self._auth_headers(),
                json=body,
            )
            self._handle_error_response(resp, "posts")
            data = resp.json()
        except httpx.HTTPError as exc:
            raise PublishError(f"Lỗi mạng khi tạo bài TikTok trên Zernio: {exc}", retryable=True) from exc
        finally:
            if should_close:
                client.close()

        post_obj = data.get("post", data) if isinstance(data, dict) else {}
        remote_id = post_obj.get("_id") or post_obj.get("id") or data.get("id")
        remote_url = post_obj.get("platformPostUrl") or post_obj.get("url")

        return PublishResult(
            channel_key=payload.channel.key,
            platform=Platform.TIKTOK,
            provider=Provider.ZERNIO,
            status=JobStatus.SUCCESS,
            idempotency_key=idempotency_key,
            remote_post_id=str(remote_id) if remote_id else None,
            remote_url=str(remote_url) if remote_url else None,
            scheduled_for=body.get("scheduledFor"),
            message="Đã gửi bài đăng TikTok qua Zernio thành công.",
            raw_response=data if isinstance(data, dict) else {"raw": data},
        )
