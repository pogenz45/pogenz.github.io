from __future__ import annotations

from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


class Platform(str, Enum):
    YOUTUBE = "youtube"
    TIKTOK = "tiktok"


class Provider(str, Enum):
    YOUTUBE_OFFICIAL = "youtube_official"
    ZERNIO = "zernio"
    UPLOAD_POST = "upload_post"


class JobStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"


class ChannelConfig(BaseModel):
    """Cấu hình 1 kênh đích (YouTube hoặc TikTok)."""

    key: str = Field(..., min_length=1, description="Mã kênh nội bộ, vd: yt_main, tiktok_1")
    platform: Platform
    provider: Provider
    display_name: str = ""
    enabled: bool = True

    # Dùng cho Zernio (lấy qua lệnh `check-zernio`)
    account_id: str | None = None
    # Dùng cho Upload-Post (tên profile kết nối trên dashboard Upload-Post)
    upload_post_user: str | None = None
    # Dùng nếu muốn tách token riêng cho nhiều kênh YouTube về sau
    youtube_token_file: str | None = None

    defaults: dict[str, Any] = Field(default_factory=dict)

    @field_validator("provider")
    @classmethod
    def validate_provider_matches_platform(cls, v: Provider, info: Any) -> Provider:
        platform = info.data.get("platform")
        if platform == Platform.YOUTUBE and v != Provider.YOUTUBE_OFFICIAL:
            raise ValueError("Kênh YouTube trong kiến trúc hybrid phải dùng provider 'youtube_official'.")
        if platform == Platform.TIKTOK and v not in (Provider.ZERNIO, Provider.UPLOAD_POST):
            raise ValueError("Kênh TikTok chỉ hỗ trợ provider 'zernio' hoặc 'upload_post'.")
        return v


class ChannelOverride(BaseModel):
    """Ghi đè nội dung/giờ đăng riêng cho từng kênh nếu cần."""

    title: str | None = None
    description: str | None = None
    caption: str | None = None
    hashtags: list[str] | None = None
    tags: list[str] | None = None
    scheduled_at: datetime | None = None
    thumbnail_path: Path | None = None
    privacy: str | None = None
    is_ai_generated: bool | None = None
    post_mode: Literal["DIRECT_POST", "MEDIA_UPLOAD"] | None = None


class PublishRequest(BaseModel):
    """Yêu cầu đăng 1 video lên 1 hoặc nhiều kênh."""

    video_path: Path
    public_video_url: str | None = None

    # Metadata mặc định dùng chung nếu không có override theo kênh
    title: str = Field(..., min_length=1, max_length=100)
    description: str = ""
    caption: str | None = None
    hashtags: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    thumbnail_path: Path | None = None

    # Lịch đăng mặc định (naive -> hiểu theo timezone mặc định; aware -> giữ timezone)
    scheduled_at: datetime | None = None
    timezone: str = "Asia/Ho_Chi_Minh"

    # Khai báo nội dung AI (ánh xạ sang containsSyntheticMedia trên YT & is_aigc trên TikTok)
    is_ai_generated: bool = False

    # Danh sách mã kênh cần đăng (None = đăng tất cả kênh đang enabled)
    target_channels: list[str] | None = None
    # Tùy biến riêng cho từng kênh (key là channel.key)
    channel_overrides: dict[str, ChannelOverride] = Field(default_factory=dict)

    # Tùy chọn vận hành
    normalize_video: bool = False
    dry_run: bool = False
    force: bool = False


class ResolvedTargetPayload(BaseModel):
    """Metadata đã hợp nhất giữa mặc định kênh + request + override riêng."""

    channel: ChannelConfig
    video_path: Path
    public_video_url: str | None = None
    title: str
    description: str
    caption: str
    tags: list[str] = Field(default_factory=list)
    thumbnail_path: Path | None = None
    scheduled_at: datetime | None = None
    timezone: str = "Asia/Ho_Chi_Minh"
    privacy: str
    is_ai_generated: bool = False
    post_mode: Literal["DIRECT_POST", "MEDIA_UPLOAD"] = "DIRECT_POST"
    extra: dict[str, Any] = Field(default_factory=dict)


class VideoMetadata(BaseModel):
    """Thông số kỹ thuật đọc từ ffprobe."""

    path: Path
    size_bytes: int
    duration_seconds: float
    width: int
    height: int
    fps: float
    video_codec: str
    audio_codec: str | None = None

    @property
    def is_vertical_or_square(self) -> bool:
        return self.height >= self.width

    @property
    def is_youtube_short_eligible(self) -> bool:
        return self.is_vertical_or_square and self.duration_seconds <= 180.0


class PublishResult(BaseModel):
    """Kết quả đăng bài trả về cho từng kênh."""

    channel_key: str
    platform: Platform
    provider: Provider
    status: JobStatus
    idempotency_key: str
    remote_post_id: str | None = None
    remote_url: str | None = None
    scheduled_for: str | None = None
    message: str = ""
    raw_response: dict[str, Any] | None = None
