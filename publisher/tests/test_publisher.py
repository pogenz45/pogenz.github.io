from __future__ import annotations

import json
import shutil
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any

import httpx
import pytest

from src.adapters.base import PublishError
from src.adapters.tiktok_upload_post import UploadPostTikTokAdapter
from src.adapters.tiktok_zernio import ZernioTikTokAdapter
from src.adapters.youtube_official import YouTubeOfficialAdapter
from src.config import AppSettings
from src.db import JobDatabase
from src.media import normalize_video_for_shorts_and_tiktok, probe_video, validate_video_for_platforms
from src.models import (
    ChannelConfig,
    ChannelOverride,
    JobStatus,
    Platform,
    Provider,
    PublishRequest,
    PublishResult,
    ResolvedTargetPayload,
)
from src.orchestrator import HybridOrchestrator


def _make_settings(tmp_path: Path) -> AppSettings:
    return AppSettings(
        base_dir=tmp_path,
        default_timezone="Asia/Ho_Chi_Minh",
        channels_config_path=tmp_path / "channels.json",
        database_path=tmp_path / "data" / "publisher.db",
        youtube_client_secrets_file=tmp_path / ".secrets" / "client_secret.json",
        youtube_token_file=tmp_path / ".secrets" / "token.json",
        zernio_api_key="test_zernio_key",
        zernio_base_url="https://zernio.com/api/v1",
        upload_post_api_key="test_upload_post_key",
        upload_post_base_url="https://api.upload-post.com",
    )


def _sample_channels(tiktok_provider: Provider = Provider.ZERNIO) -> list[ChannelConfig]:
    return [
        ChannelConfig(
            key="yt_main",
            platform=Platform.YOUTUBE,
            provider=Provider.YOUTUBE_OFFICIAL,
            display_name="YouTube Main",
            defaults={"privacy_status": "public", "category_id": "22", "made_for_kids": False},
        ),
        ChannelConfig(
            key="tiktok_1",
            platform=Platform.TIKTOK,
            provider=tiktok_provider,
            display_name="TikTok 1",
            account_id="acc_tt_1",
            upload_post_user="profile_tt_1",
            defaults={"privacy_level": "PUBLIC_TO_EVERYONE", "allow_comment": True},
        ),
        ChannelConfig(
            key="tiktok_2",
            platform=Platform.TIKTOK,
            provider=tiktok_provider,
            display_name="TikTok 2",
            account_id="acc_tt_2",
            upload_post_user="profile_tt_2",
            defaults={"privacy_level": "PUBLIC_TO_EVERYONE", "allow_comment": True},
        ),
    ]


class _FakeYouTubeRequest:
    def __init__(self, response: dict[str, Any]) -> None:
        self._response = response
        self._done = False

    def next_chunk(self):
        self._done = True
        return None, self._response

    def execute(self):
        return self._response


class _FakeYouTubeService:
    def __init__(self) -> None:
        self.insert_bodies: list[dict[str, Any]] = []
        self.thumbnail_calls: list[str] = []

    def videos(self):
        outer = self

        class _VideosResource:
            def insert(self, part, body, media_body):
                outer.insert_bodies.append(body)
                return _FakeYouTubeRequest({"id": "yt_vid_123"})

            def list(self, part, id):
                return _FakeYouTubeRequest(
                    {"items": [{"id": id, "processingDetails": {"processingStatus": "succeeded"}}]}
                )

        return _VideosResource()

    def thumbnails(self):
        outer = self

        class _ThumbsResource:
            def set(self, videoId, media_body):
                outer.thumbnail_calls.append(videoId)
                return _FakeYouTubeRequest({"items": [{"default": {"url": "https://img"}}]})

        return _ThumbsResource()


def test_youtube_official_scheduling_and_thumbnail(tmp_path: Path) -> None:
    settings = _make_settings(tmp_path)
    video = tmp_path / "sample.mp4"
    video.write_bytes(b"fake_mp4_content")
    thumb = tmp_path / "thumb.jpg"
    thumb.write_bytes(b"fake_jpg_content")

    fake_service = _FakeYouTubeService()
    adapter = YouTubeOfficialAdapter(
        settings,
        service_factory=lambda _p: fake_service,
        sleep_fn=lambda _s: None,
    )
    ch = _sample_channels()[0]
    payload = ResolvedTargetPayload(
        channel=ch,
        video_path=video,
        title="Demo Shorts #shorts",
        description="Mô tả test",
        caption="Demo Shorts #shorts",
        tags=["shorts", "ai"],
        thumbnail_path=thumb,
        scheduled_at=datetime(2026, 12, 1, 19, 0, 0),
        timezone="Asia/Ho_Chi_Minh",
        privacy="public",
        is_ai_generated=True,
        extra=ch.defaults,
    )

    res = adapter.publish(payload, "idem_yt_1")
    assert res.status == JobStatus.SUCCESS
    assert res.remote_post_id == "yt_vid_123"
    assert res.remote_url == "https://www.youtube.com/watch?v=yt_vid_123"

    sent_body = fake_service.insert_bodies[0]
    # Khi hẹn giờ publishAt, privacyStatus BẮT BUỘC phải là 'private' và publishAt là UTC (19:00+07 -> 12:00Z)
    assert sent_body["status"]["privacyStatus"] == "private"
    assert sent_body["status"]["publishAt"] == "2026-12-01T12:00:00Z"
    assert sent_body["status"]["containsSyntheticMedia"] is True
    assert fake_service.thumbnail_calls == ["yt_vid_123"]


def test_zernio_presigned_upload_and_shared_url_for_two_tiktok_channels(tmp_path: Path) -> None:
    settings = _make_settings(tmp_path)
    video = tmp_path / "clip.mp4"
    video.write_bytes(b"0123456789abcdef")

    calls: list[tuple[str, str, dict[str, str]]] = []
    post_payloads: list[dict[str, Any]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append((request.method, str(request.url), dict(request.headers)))
        if request.url.path.endswith("/media/presign"):
            assert request.headers.get("authorization") == "Bearer test_zernio_key"
            return httpx.Response(
                200,
                json={
                    "uploadUrl": "https://r2.storage.example/upload/signed-1",
                    "publicUrl": "https://zernio.com/temp/signed-1.mp4",
                    "expiresIn": 3600,
                },
            )
        if str(request.url) == "https://r2.storage.example/upload/signed-1":
            # Khi PUT lên R2 presigned URL tuyệt đối KHÔNG gửi header Authorization
            assert "authorization" not in {k.lower() for k in request.headers.keys()}
            assert request.headers.get("content-type") == "video/mp4"
            return httpx.Response(200)
        if request.url.path.endswith("/posts"):
            body = json.loads(request.content.decode("utf-8"))
            post_payloads.append(body)
            acc = body["platforms"][0]["accountId"]
            return httpx.Response(200, json={"post": {"_id": f"post_{acc}", "url": f"https://tiktok.com/{acc}"}})
        return httpx.Response(404, json={"error": "not found"})

    mock_client = httpx.Client(transport=httpx.MockTransport(handler))
    fake_yt = _FakeYouTubeService()

    channels = _sample_channels(Provider.ZERNIO)
    db = JobDatabase(settings.database_path)
    orch = HybridOrchestrator(
        settings,
        channels,
        db,
        adapters={
            Provider.YOUTUBE_OFFICIAL: YouTubeOfficialAdapter(settings, service_factory=lambda _p: fake_yt),
            Provider.ZERNIO: ZernioTikTokAdapter(settings, http_client=mock_client),
            Provider.UPLOAD_POST: UploadPostTikTokAdapter(settings),
        },
        sleep_fn=lambda _s: None,
    )

    req = PublishRequest(
        video_path=video,
        title="Video AI test",
        caption="Caption chung",
        hashtags=["ai", "tiktok"],
        scheduled_at=datetime(2026, 12, 1, 19, 0, 0),
        is_ai_generated=True,
        channel_overrides={
            "tiktok_2": ChannelOverride(
                caption="Caption riêng kênh 2",
                scheduled_at=datetime(2026, 12, 1, 20, 30, 0),
            )
        },
    )

    results = orch.run(req)
    assert len(results) == 3
    assert all(r.status == JobStatus.SUCCESS for r in results)

    # Kiểm tra tối ưu: presign và PUT chỉ được gọi ĐÚNG 1 LẦN dù đăng cho 2 kênh TikTok!
    presign_calls = [c for c in calls if c[1].endswith("/media/presign")]
    put_calls = [c for c in calls if c[0] == "PUT"]
    assert len(presign_calls) == 1
    assert len(put_calls) == 1
    assert len(post_payloads) == 2

    assert post_payloads[0]["platforms"][0]["accountId"] == "acc_tt_1"
    assert post_payloads[0]["scheduledFor"] == "2026-12-01T19:00:00"
    assert post_payloads[0]["tiktokSettings"]["is_aigc"] is True
    assert post_payloads[0]["tiktokSettings"]["content_preview_confirmed"] is True

    assert post_payloads[1]["platforms"][0]["accountId"] == "acc_tt_2"
    assert post_payloads[1]["scheduledFor"] == "2026-12-01T20:30:00"
    assert "Caption riêng kênh 2" in post_payloads[1]["content"]

    # Chạy lại lần 2 cùng request -> phải bị SKIPPED nhờ chống trùng lặp SQLite!
    results_second = orch.run(req)
    assert all(r.status == JobStatus.SKIPPED for r in results_second)
    assert len(post_payloads) == 2  # Không bắn thêm API nào


def test_upload_post_adapter_and_smart_retry(tmp_path: Path) -> None:
    settings = _make_settings(tmp_path)
    video = tmp_path / "uclip.mp4"
    video.write_bytes(b"mp4data")

    attempt_counter = {"tiktok_1": 0, "tiktok_2": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers.get("authorization") == "Apikey test_upload_post_key"
        raw = request.content.decode("utf-8", errors="ignore")
        if "profile_tt_1" in raw:
            attempt_counter["tiktok_1"] += 1
            if attempt_counter["tiktok_1"] == 1:
                return httpx.Response(503, json={"error": "temporary unavailable"})
            return httpx.Response(200, json={"request_id": "up_1", "results": {"tiktok": {"url": "https://tiktok.com/up1"}}})
        # Kênh 2 trả về 403 -> KHÔNG được retry!
        attempt_counter["tiktok_2"] += 1
        return httpx.Response(403, json={"error": "plan does not allow tiktok"})

    mock_client = httpx.Client(transport=httpx.MockTransport(handler))
    channels = [c for c in _sample_channels(Provider.UPLOAD_POST) if c.platform == Platform.TIKTOK]
    db = JobDatabase(settings.database_path)

    orch = HybridOrchestrator(
        settings,
        channels,
        db,
        adapters={Provider.UPLOAD_POST: UploadPostTikTokAdapter(settings, http_client=mock_client)},
        max_retries=3,
        sleep_fn=lambda _s: None,
    )

    req = PublishRequest(video_path=video, title="Test Upload-Post")
    results = orch.run(req)

    by_key = {r.channel_key: r for r in results}
    assert by_key["tiktok_1"].status == JobStatus.SUCCESS
    assert attempt_counter["tiktok_1"] == 2  # Retry 1 lần sau 503 rồi thành công

    assert by_key["tiktok_2"].status == JobStatus.FAILED
    assert attempt_counter["tiktok_2"] == 1  # Lỗi 403 dừng ngay, không retry


def test_dry_run_does_not_write_db(tmp_path: Path) -> None:
    settings = _make_settings(tmp_path)
    video = tmp_path / "dry.mp4"
    video.write_bytes(b"dry_data")

    db = JobDatabase(settings.database_path)
    orch = HybridOrchestrator(settings, _sample_channels(Provider.ZERNIO), db)
    results = orch.run(PublishRequest(video_path=video, title="Dry test", dry_run=True))

    assert len(results) == 3
    assert all(r.status == JobStatus.SKIPPED for r in results)
    assert db.list_recent() == []


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="FFmpeg không có sẵn trong PATH")
def test_ffmpeg_probe_and_normalize_real_video(tmp_path: Path) -> None:
    raw_video = tmp_path / "raw_landscape.mp4"
    norm_video = tmp_path / "clean_vertical.mp4"

    # Tạo 1 video 1 giây ngang 640x360 kèm audio sine wave bằng ffmpeg thật
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "color=c=blue:s=640x360:d=1:r=25",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=440:duration=1",
            "-c:v",
            "libx264",
            "-c:a",
            "aac",
            str(raw_video),
        ],
        check=True,
        capture_output=True,
    )

    raw_meta = probe_video(raw_video)
    assert raw_meta.width == 640 and raw_meta.height == 360
    assert raw_meta.is_youtube_short_eligible is False

    normalize_video_for_shorts_and_tiktok(raw_video, norm_video)
    norm_meta = probe_video(norm_video)
    assert norm_meta.width == 1080 and norm_meta.height == 1920
    assert norm_meta.video_codec == "h264"
    assert norm_meta.audio_codec == "aac"
    assert norm_meta.is_youtube_short_eligible is True
    assert validate_video_for_platforms(norm_meta, {Platform.YOUTUBE, Platform.TIKTOK}) == []
