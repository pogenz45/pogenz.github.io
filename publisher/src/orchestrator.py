from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Callable

from src.adapters.base import BasePublisherAdapter, PublishError, to_aware_datetime
from src.adapters.tiktok_upload_post import UploadPostTikTokAdapter
from src.adapters.tiktok_zernio import ZernioTikTokAdapter
from src.adapters.youtube_official import YouTubeOfficialAdapter
from src.config import AppSettings
from src.db import JobDatabase, build_idempotency_key, compute_file_sha256
from src.media import normalize_video_for_shorts_and_tiktok
from src.models import (
    ChannelConfig,
    JobStatus,
    Platform,
    Provider,
    PublishRequest,
    PublishResult,
    ResolvedTargetPayload,
)


def _format_caption(base_text: str, hashtags: list[str]) -> str:
    clean_tags = []
    for tag in hashtags:
        t = tag.strip()
        if not t:
            continue
        clean_tags.append(t if t.startswith("#") else f"#{t}")
    if not clean_tags:
        return base_text.strip()
    tag_line = " ".join(clean_tags)
    if not base_text.strip():
        return tag_line
    return f"{base_text.strip()}\n\n{tag_line}"


class HybridOrchestrator:
    """
    Điều phối đăng 1 video lên nhiều kênh theo kiến trúc Hybrid:
    - YouTube -> YouTubeOfficialAdapter ($0)
    - TikTok  -> ZernioTikTokAdapter ($0 cho 2 kênh) hoặc UploadPostTikTokAdapter
    Tích hợp:
    - Chống đăng trùng bằng SQLite idempotency_key
    - Smart Retry (chỉ retry 429/5xx/network, KHÔNG retry 4xx)
    - Tái sử dụng Zernio presigned publicUrl khi đăng chung 1 file lên cả 2 kênh TikTok
    """

    def __init__(
        self,
        settings: AppSettings,
        channels: list[ChannelConfig],
        db: JobDatabase,
        *,
        adapters: dict[Provider, BasePublisherAdapter] | None = None,
        max_retries: int = 3,
        sleep_fn: Callable[[float], None] = time.sleep,
    ) -> None:
        self.settings = settings
        self.channels = channels
        self.db = db
        self.max_retries = max_retries
        self._sleep = sleep_fn

        self.adapters: dict[Provider, BasePublisherAdapter] = adapters or {
            Provider.YOUTUBE_OFFICIAL: YouTubeOfficialAdapter(settings, sleep_fn=sleep_fn),
            Provider.ZERNIO: ZernioTikTokAdapter(settings),
            Provider.UPLOAD_POST: UploadPostTikTokAdapter(settings),
        }

    def _select_channels(self, request: PublishRequest) -> list[ChannelConfig]:
        enabled_map = {ch.key: ch for ch in self.channels if ch.enabled}
        if not request.target_channels:
            return list(enabled_map.values())

        selected: list[ChannelConfig] = []
        for key in request.target_channels:
            if key not in enabled_map:
                raise ValueError(
                    f"Mã kênh '{key}' không tồn tại hoặc đang bị tắt (enabled=false). "
                    f"Các kênh khả dụng: {list(enabled_map.keys())}"
                )
            selected.append(enabled_map[key])
        return selected

    def _resolve_payload(
        self,
        channel: ChannelConfig,
        request: PublishRequest,
        video_path: Path,
        shared_public_url: str | None = None,
    ) -> ResolvedTargetPayload:
        ov = request.channel_overrides.get(channel.key)
        defaults = channel.defaults

        title = (ov.title if ov and ov.title is not None else request.title).strip()
        description = (
            ov.description if ov and ov.description is not None else request.description
        ).strip()
        hashtags = ov.hashtags if ov and ov.hashtags is not None else request.hashtags

        base_caption = (
            ov.caption
            if ov and ov.caption is not None
            else (request.caption if request.caption is not None else title)
        )
        caption = _format_caption(base_caption, hashtags)

        default_tags = list(defaults.get("default_tags", []))
        tags = ov.tags if ov and ov.tags is not None else (request.tags or default_tags)

        scheduled_at = (
            ov.scheduled_at if ov and ov.scheduled_at is not None else request.scheduled_at
        )
        thumbnail_path = (
            ov.thumbnail_path if ov and ov.thumbnail_path is not None else request.thumbnail_path
        )

        default_privacy = (
            defaults.get("privacy_status", "public")
            if channel.platform == Platform.YOUTUBE
            else defaults.get("privacy_level", "PUBLIC_TO_EVERYONE")
        )
        privacy = ov.privacy if ov and ov.privacy is not None else str(default_privacy)

        default_ai = bool(
            defaults.get("contains_synthetic_media", False)
            if channel.platform == Platform.YOUTUBE
            else defaults.get("is_aigc", False)
        )
        is_ai = (
            ov.is_ai_generated
            if ov and ov.is_ai_generated is not None
            else (request.is_ai_generated or default_ai)
        )

        post_mode = (
            ov.post_mode
            if ov and ov.post_mode is not None
            else defaults.get("post_mode", "DIRECT_POST")
        )

        return ResolvedTargetPayload(
            channel=channel,
            video_path=video_path,
            public_video_url=shared_public_url or request.public_video_url,
            title=title,
            description=description or caption,
            caption=caption,
            tags=tags,
            thumbnail_path=thumbnail_path,
            scheduled_at=scheduled_at,
            timezone=request.timezone or self.settings.default_timezone,
            privacy=privacy,
            is_ai_generated=is_ai,
            post_mode=post_mode,
            extra=dict(defaults),
        )

    def _execute_with_retry(
        self,
        adapter: BasePublisherAdapter,
        payload: ResolvedTargetPayload,
        idempotency_key: str,
    ) -> PublishResult:
        last_err: PublishError | None = None
        for attempt in range(1, self.max_retries + 1):
            try:
                return adapter.publish(payload, idempotency_key)
            except PublishError as exc:
                last_err = exc
                if not exc.retryable or attempt >= self.max_retries:
                    raise
                backoff = float(2**attempt)
                self._sleep(backoff)
        assert last_err is not None
        raise last_err

    def run(self, request: PublishRequest) -> list[PublishResult]:
        if not request.video_path.exists():
            raise FileNotFoundError(f"Không tìm thấy file video: {request.video_path}")

        target_channels = self._select_channels(request)
        if not target_channels:
            return []

        working_video = request.video_path
        if request.normalize_video and not request.dry_run:
            norm_dir = self.settings.base_dir / "output" / "normalized"
            norm_path = norm_dir / f"{request.video_path.stem}_clean.mp4"
            working_video = normalize_video_for_shorts_and_tiktok(request.video_path, norm_path)

        video_sha256 = compute_file_sha256(working_video)

        # Nếu có >= 2 kênh TikTok cùng dùng Zernio và chưa có public URL,
        # upload presigned 1 lần duy nhất rồi dùng chung cho cả 2 kênh!
        shared_zernio_url: str | None = request.public_video_url
        zernio_targets = [ch for ch in target_channels if ch.provider == Provider.ZERNIO]
        if not request.dry_run and not shared_zernio_url and len(zernio_targets) >= 2:
            zernio_adapter = self.adapters[Provider.ZERNIO]
            if isinstance(zernio_adapter, ZernioTikTokAdapter):
                # Chỉ upload trước nếu ít nhất 1 kênh Zernio thực sự cần đăng (chưa bị skip idempotency)
                needs_upload = False
                for ch in zernio_targets:
                    p_check = self._resolve_payload(ch, request, working_video)
                    sched_key = (
                        to_aware_datetime(p_check.scheduled_at, p_check.timezone).isoformat()
                        if p_check.scheduled_at
                        else None
                    )
                    idem = build_idempotency_key(video_sha256, ch.key, sched_key)
                    existing = self.db.get_by_idempotency_key(idem)
                    if request.force or not existing or existing.get("status") != JobStatus.SUCCESS.value:
                        needs_upload = True
                        break
                if needs_upload:
                    shared_zernio_url = zernio_adapter.upload_media_presigned(working_video)

        results: list[PublishResult] = []
        for channel in target_channels:
            adapter = self.adapters[channel.provider]
            shared_url_for_ch = shared_zernio_url if channel.provider == Provider.ZERNIO else request.public_video_url
            payload = self._resolve_payload(channel, request, working_video, shared_url_for_ch)

            sched_key = (
                to_aware_datetime(payload.scheduled_at, payload.timezone).isoformat()
                if payload.scheduled_at
                else None
            )
            idem_key = build_idempotency_key(video_sha256, channel.key, sched_key)

            existing = self.db.get_by_idempotency_key(idem_key)
            if existing and existing.get("status") == JobStatus.SUCCESS.value and not request.force:
                results.append(
                    PublishResult(
                        channel_key=channel.key,
                        platform=channel.platform,
                        provider=channel.provider,
                        status=JobStatus.SKIPPED,
                        idempotency_key=idem_key,
                        remote_post_id=existing.get("remote_post_id"),
                        remote_url=existing.get("remote_url"),
                        scheduled_for=existing.get("scheduled_for"),
                        message="Đã đăng thành công trước đó (chống trùng lặp). Truyền --force nếu muốn đăng lại.",
                    )
                )
                continue

            if request.dry_run:
                preview: dict[str, Any] = adapter.build_request_preview(payload)
                results.append(
                    PublishResult(
                        channel_key=channel.key,
                        platform=channel.platform,
                        provider=channel.provider,
                        status=JobStatus.SKIPPED,
                        idempotency_key=idem_key,
                        scheduled_for=sched_key,
                        message="[DRY-RUN] Chưa gọi API thật.",
                        raw_response=preview,
                    )
                )
                continue

            self.db.upsert_job_start(
                idempotency_key=idem_key,
                channel_key=channel.key,
                platform=channel.platform,
                provider=channel.provider,
                video_path=working_video,
                video_sha256=video_sha256,
                title=payload.title,
                scheduled_for=sched_key,
            )

            try:
                res = self._execute_with_retry(adapter, payload, idem_key)
                self.db.mark_success(
                    idempotency_key=idem_key,
                    remote_post_id=res.remote_post_id,
                    remote_url=res.remote_url,
                    raw_response=res.raw_response,
                )
                results.append(res)
            except PublishError as exc:
                self.db.mark_failed(
                    idempotency_key=idem_key,
                    error_message=str(exc),
                    raw_response=exc.raw_response,
                )
                results.append(
                    PublishResult(
                        channel_key=channel.key,
                        platform=channel.platform,
                        provider=channel.provider,
                        status=JobStatus.FAILED,
                        idempotency_key=idem_key,
                        scheduled_for=sched_key,
                        message=str(exc),
                        raw_response=exc.raw_response,
                    )
                )

        return results
