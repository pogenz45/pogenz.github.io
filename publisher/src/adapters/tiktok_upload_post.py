from __future__ import annotations

from typing import Any

import httpx

from src.adapters.base import BasePublisherAdapter, PublishError, to_aware_datetime
from src.config import AppSettings
from src.models import JobStatus, Platform, Provider, PublishResult, ResolvedTargetPayload


class UploadPostTikTokAdapter(BasePublisherAdapter):
    """
    Adapter dự phòng / thay thế cho TikTok qua Upload-Post (upload-post.com).
    - Endpoint: POST https://api.upload-post.com/api/upload (multipart/form-data)
    - Header: Authorization: Apikey <UPLOAD_POST_API_KEY>
    - Hỗ trợ cả DIRECT_POST (đăng thẳng) lẫn MEDIA_UPLOAD (đẩy vào Inbox/Draft)
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

    def _build_form_fields(
        self,
        payload: ResolvedTargetPayload,
        idempotency_key: str,
    ) -> dict[str, Any]:
        user_profile = payload.channel.upload_post_user
        if not user_profile:
            raise PublishError(
                f"Kênh '{payload.channel.key}' chưa cấu hình `upload_post_user` trong channels.json.",
                retryable=False,
            )

        fields: dict[str, Any] = {
            "user": user_profile,
            "platform[]": "tiktok",
            "title": payload.caption[:2200],
            "privacy_level": payload.privacy or "PUBLIC_TO_EVERYONE",
            "post_mode": payload.post_mode or "DIRECT_POST",
            "disable_comment": "false" if payload.extra.get("allow_comment", True) else "true",
            "external_id": idempotency_key,
        }
        if payload.scheduled_at is not None:
            aware_local = to_aware_datetime(payload.scheduled_at, payload.timezone)
            fields["scheduled_date"] = aware_local.isoformat()
            fields["timezone"] = payload.timezone
        if payload.public_video_url:
            fields["video"] = payload.public_video_url
        return fields

    def build_request_preview(self, payload: ResolvedTargetPayload) -> dict[str, Any]:
        fields = {
            "user": payload.channel.upload_post_user or "<MISSING_UPLOAD_POST_USER>",
            "platform[]": "tiktok",
            "title": payload.caption[:2200],
            "privacy_level": payload.privacy or "PUBLIC_TO_EVERYONE",
            "post_mode": payload.post_mode or "DIRECT_POST",
            "disable_comment": "false" if payload.extra.get("allow_comment", True) else "true",
            "video": payload.public_video_url or f"@{payload.video_path}",
        }
        if payload.scheduled_at is not None:
            aware_local = to_aware_datetime(payload.scheduled_at, payload.timezone)
            fields["scheduled_date"] = aware_local.isoformat()
            fields["timezone"] = payload.timezone

        return {
            "endpoint": f"POST {self.settings.upload_post_base_url}/api/upload (multipart/form-data)",
            "fields": fields,
        }

    def publish(self, payload: ResolvedTargetPayload, idempotency_key: str) -> PublishResult:
        if not self.settings.upload_post_api_key:
            raise PublishError(
                "Thiếu `UPLOAD_POST_API_KEY` trong file `.env`.",
                retryable=False,
            )

        fields = self._build_form_fields(payload, idempotency_key)
        headers = {"Authorization": f"Apikey {self.settings.upload_post_api_key}"}
        url = f"{self.settings.upload_post_base_url}/api/upload"

        client = self._client()
        should_close = self._external_client is None
        try:
            if payload.public_video_url:
                resp = client.post(url, headers=headers, data=fields)
            else:
                if not payload.video_path.exists():
                    raise PublishError(f"Không tìm thấy file video: {payload.video_path}", retryable=False)
                with payload.video_path.open("rb") as fh:
                    files = {"video": (payload.video_path.name, fh, "video/mp4")}
                    resp = client.post(url, headers=headers, data=fields, files=files)

            if not (200 <= resp.status_code < 300):
                try:
                    err_body = resp.json()
                except Exception:
                    err_body = {"raw_text": resp.text[:1000]}
                retryable = resp.status_code in (429, 500, 502, 503, 504)
                raise PublishError(
                    f"Upload-Post API lỗi HTTP {resp.status_code}: {err_body}",
                    retryable=retryable,
                    status_code=resp.status_code,
                    raw_response=err_body if isinstance(err_body, dict) else None,
                )

            data = resp.json()
        except httpx.HTTPError as exc:
            raise PublishError(f"Lỗi mạng khi gọi Upload-Post API: {exc}", retryable=True) from exc
        finally:
            if should_close:
                client.close()

        remote_id = data.get("request_id") or data.get("job_id") or data.get("id")
        remote_url = None
        results = data.get("results", {})
        if isinstance(results, dict):
            tiktok_res = results.get("tiktok", {})
            if isinstance(tiktok_res, dict):
                remote_url = tiktok_res.get("url")
                remote_id = remote_id or tiktok_res.get("publish_id")

        return PublishResult(
            channel_key=payload.channel.key,
            platform=Platform.TIKTOK,
            provider=Provider.UPLOAD_POST,
            status=JobStatus.SUCCESS,
            idempotency_key=idempotency_key,
            remote_post_id=str(remote_id) if remote_id else None,
            remote_url=str(remote_url) if remote_url else None,
            scheduled_for=fields.get("scheduled_date"),
            message="Đã gửi bài đăng TikTok qua Upload-Post thành công.",
            raw_response=data if isinstance(data, dict) else {"raw": data},
        )
