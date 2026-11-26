from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from src.models import PublishResult, ResolvedTargetPayload


class PublishError(Exception):
    """Lỗi khi gọi API đăng bài lên nền tảng."""

    def __init__(
        self,
        message: str,
        *,
        retryable: bool = False,
        status_code: int | None = None,
        raw_response: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.retryable = retryable
        self.status_code = status_code
        self.raw_response = raw_response


def get_zoneinfo(tz_name: str) -> timezone | ZoneInfo:
    try:
        return ZoneInfo(tz_name)
    except ZoneInfoNotFoundError:
        if tz_name in ("Asia/Ho_Chi_Minh", "Asia/Saigon", "ICT"):
            return timezone(timedelta(hours=7))
        if tz_name.upper() == "UTC":
            return timezone.utc
        raise


def to_aware_datetime(dt: datetime, tz_name: str) -> datetime:
    tz = get_zoneinfo(tz_name)
    if dt.tzinfo is None:
        return dt.replace(tzinfo=tz)
    return dt.astimezone(tz)


class BasePublisherAdapter(ABC):
    """Interface chung cho mọi nền tảng/provider để dễ dàng thay thế không đụng code lõi."""

    @abstractmethod
    def build_request_preview(self, payload: ResolvedTargetPayload) -> dict[str, Any]:
        """Trả về bản xem trước payload sẽ gửi (dùng cho --dry-run và audit)."""

    @abstractmethod
    def publish(self, payload: ResolvedTargetPayload, idempotency_key: str) -> PublishResult:
        """Thực hiện upload và đăng/hẹn giờ bài viết."""
