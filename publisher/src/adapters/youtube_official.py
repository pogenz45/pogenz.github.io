from __future__ import annotations

import time
from datetime import timezone
from pathlib import Path
from typing import Any, Callable

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload

from src.adapters.base import BasePublisherAdapter, PublishError, to_aware_datetime
from src.config import AppSettings
from src.models import JobStatus, Platform, Provider, PublishResult, ResolvedTargetPayload


YOUTUBE_SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.readonly",
]


class YouTubeOfficialAdapter(BasePublisherAdapter):
    """
    Adapter đăng video trực tiếp qua YouTube Data API v3 (Miễn phí - 100 uploads/ngày mặc định).
    - Hỗ trợ Resumable Upload cho file lớn
    - Hỗ trợ hẹn giờ native (`publishAt` kèm `privacyStatus='private'`)
    - Hỗ trợ khai báo nội dung AI (`containsSyntheticMedia`)
    - Hỗ trợ chờ xử lý xong (`processingStatus == 'succeeded'`) rồi mới gắn Custom Thumbnail
    """

    def __init__(
        self,
        settings: AppSettings,
        *,
        service_factory: Callable[[Path], Any] | None = None,
        sleep_fn: Callable[[float], None] = time.sleep,
    ) -> None:
        self.settings = settings
        self._service_factory = service_factory
        self._sleep = sleep_fn

    def _resolve_token_path(self, payload: ResolvedTargetPayload | None = None) -> Path:
        if payload and payload.channel.youtube_token_file:
            p = Path(payload.channel.youtube_token_file)
            return p if p.is_absolute() else (self.settings.base_dir / p)
        return self.settings.youtube_token_file

    def authenticate_interactive(self, token_path: Path | None = None) -> Path:
        """Mở trình duyệt đăng nhập OAuth2 Desktop Flow 1 lần để lưu refresh_token."""
        secrets_file = self.settings.youtube_client_secrets_file
        if not secrets_file.exists():
            raise FileNotFoundError(
                f"Chưa tìm thấy file OAuth client secret tại: {secrets_file}. "
                "Hãy tải từ Google Cloud Console (APIs & Services -> Credentials -> OAuth Client ID -> Desktop app)."
            )

        target_token = token_path or self.settings.youtube_token_file
        target_token.parent.mkdir(parents=True, exist_ok=True)

        flow = InstalledAppFlow.from_client_secrets_file(str(secrets_file), YOUTUBE_SCOPES)
        creds = flow.run_local_server(port=0, access_type="offline", prompt="consent")
        target_token.write_text(creds.to_json(), encoding="utf-8")
        return target_token

    def _get_service(self, token_path: Path) -> Any:
        if self._service_factory is not None:
            return self._service_factory(token_path)

        if not token_path.exists():
            raise PublishError(
                f"Chưa có YouTube OAuth token tại {token_path}. Hãy chạy `python -m src.cli auth-youtube` trước.",
                retryable=False,
            )

        creds = Credentials.from_authorized_user_file(str(token_path), YOUTUBE_SCOPES)
        if not creds.valid:
            if creds.expired and creds.refresh_token:
                try:
                    creds.refresh(Request())
                    token_path.write_text(creds.to_json(), encoding="utf-8")
                except Exception as exc:
                    raise PublishError(
                        "Không thể refresh YouTube token (rất có thể Google OAuth đang ở chế độ Testing bị hết hạn sau 7 ngày). "
                        f"Hãy chuyển OAuth Consent Screen sang In Production và chạy lại `auth-youtube`. Chi tiết: {exc}",
                        retryable=False,
                    ) from exc
            else:
                raise PublishError(
                    "YouTube token không hợp lệ hoặc thiếu refresh_token. Hãy chạy lại `auth-youtube`.",
                    retryable=False,
                )

        return build("youtube", "v3", credentials=creds, cache_discovery=False)

    def build_video_body(self, payload: ResolvedTargetPayload) -> dict[str, Any]:
        snippet: dict[str, Any] = {
            "title": payload.title[:100],
            "description": payload.description[:5000],
            "categoryId": str(payload.extra.get("category_id", "22")),
        }
        if payload.tags:
            snippet["tags"] = payload.tags[:30]

        status: dict[str, Any] = {
            "selfDeclaredMadeForKids": bool(payload.extra.get("made_for_kids", False)),
            "containsSyntheticMedia": bool(payload.is_ai_generated),
        }

        if payload.scheduled_at is not None:
            aware_local = to_aware_datetime(payload.scheduled_at, payload.timezone)
            utc_dt = aware_local.astimezone(timezone.utc)
            # Bắt buộc theo spec YouTube: muốn dùng publishAt thì privacyStatus phải là 'private'
            status["privacyStatus"] = "private"
            status["publishAt"] = utc_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
        else:
            status["privacyStatus"] = payload.privacy or "public"

        return {"snippet": snippet, "status": status}

    def build_request_preview(self, payload: ResolvedTargetPayload) -> dict[str, Any]:
        return {
            "endpoint": "YouTube Data API v3 videos.insert (Resumable)",
            "token_file": str(self._resolve_token_path(payload)),
            "video_path": str(payload.video_path),
            "thumbnail_path": str(payload.thumbnail_path) if payload.thumbnail_path else None,
            "body": self.build_video_body(payload),
        }

    def _wait_and_set_thumbnail(
        self,
        service: Any,
        video_id: str,
        thumbnail_path: Path,
        timeout_seconds: int = 120,
    ) -> str:
        if not thumbnail_path.exists():
            return f"Bỏ qua thumbnail (không thấy file {thumbnail_path})."

        deadline = time.monotonic() + timeout_seconds
        processed = False
        while time.monotonic() < deadline:
            resp = (
                service.videos()
                .list(part="processingDetails", id=video_id)
                .execute()
            )
            items = resp.get("items", [])
            if items:
                proc_status = items[0].get("processingDetails", {}).get("processingStatus")
                if proc_status == "succeeded":
                    processed = True
                    break
                if proc_status in ("failed", "terminated"):
                    return f"YouTube xử lý video trạng thái '{proc_status}', không thể gắn thumbnail."
            self._sleep(5.0)

        if not processed:
            return "Quá thời gian chờ YouTube xử lý video để gắn thumbnail (video vẫn đã lên thành công)."

        media = MediaFileUpload(str(thumbnail_path))
        service.thumbnails().set(videoId=video_id, media_body=media).execute()
        return "Đã gắn custom thumbnail thành công."

    def publish(self, payload: ResolvedTargetPayload, idempotency_key: str) -> PublishResult:
        token_path = self._resolve_token_path(payload)
        service = self._get_service(token_path)
        body = self.build_video_body(payload)

        media = MediaFileUpload(
            str(payload.video_path),
            chunksize=8 * 1024 * 1024,
            resumable=True,
        )
        request = service.videos().insert(
            part="snippet,status",
            body=body,
            media_body=media,
        )

        response: dict[str, Any] | None = None
        try:
            while response is None:
                _, response = request.next_chunk()
        except HttpError as exc:
            status_code = exc.resp.status if exc.resp else None
            retryable = status_code in (429, 500, 502, 503, 504)
            raise PublishError(
                f"YouTube API lỗi HTTP {status_code}: {exc}",
                retryable=retryable,
                status_code=status_code,
            ) from exc
        except Exception as exc:
            raise PublishError(
                f"Lỗi kết nối khi upload lên YouTube: {exc}",
                retryable=True,
            ) from exc

        video_id = response.get("id")
        remote_url = f"https://www.youtube.com/watch?v={video_id}" if video_id else None
        msg = "Upload YouTube thành công."

        if video_id and payload.thumbnail_path:
            try:
                thumb_msg = self._wait_and_set_thumbnail(service, video_id, payload.thumbnail_path)
                msg = f"{msg} {thumb_msg}"
            except HttpError as exc:
                msg = f"{msg} Cảnh báo gắn thumbnail lỗi: {exc}"

        return PublishResult(
            channel_key=payload.channel.key,
            platform=Platform.YOUTUBE,
            provider=Provider.YOUTUBE_OFFICIAL,
            status=JobStatus.SUCCESS,
            idempotency_key=idempotency_key,
            remote_post_id=video_id,
            remote_url=remote_url,
            scheduled_for=body["status"].get("publishAt"),
            message=msg,
            raw_response=response,
        )
