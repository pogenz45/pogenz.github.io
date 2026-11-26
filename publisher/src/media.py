from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

from src.models import Platform, VideoMetadata


def _parse_fps(rate_str: str | None) -> float:
    if not rate_str or rate_str == "0/0":
        return 0.0
    if "/" in rate_str:
        num, den = rate_str.split("/", 1)
        den_f = float(den)
        return float(num) / den_f if den_f else 0.0
    return float(rate_str)


def probe_video(video_path: Path) -> VideoMetadata:
    """Đọc thông số video bằng ffprobe."""
    if not video_path.exists():
        raise FileNotFoundError(f"Không tìm thấy file video: {video_path}")

    ffprobe_bin = shutil.which("ffprobe")
    if not ffprobe_bin:
        raise RuntimeError("Không tìm thấy `ffprobe` trong PATH. Hãy cài FFmpeg.")

    cmd = [
        ffprobe_bin,
        "-v",
        "error",
        "-print_format",
        "json",
        "-show_format",
        "-show_streams",
        str(video_path),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=True)
    data = json.loads(proc.stdout)

    streams = data.get("streams", [])
    video_stream = next((s for s in streams if s.get("codec_type") == "video"), None)
    audio_stream = next((s for s in streams if s.get("codec_type") == "audio"), None)
    if not video_stream:
        raise ValueError(f"File không có video stream hợp lệ: {video_path}")

    fmt = data.get("format", {})
    duration = float(fmt.get("duration") or video_stream.get("duration") or 0.0)
    fps = _parse_fps(video_stream.get("avg_frame_rate") or video_stream.get("r_frame_rate"))

    return VideoMetadata(
        path=video_path,
        size_bytes=video_path.stat().st_size,
        duration_seconds=duration,
        width=int(video_stream.get("width", 0)),
        height=int(video_stream.get("height", 0)),
        fps=round(fps, 2),
        video_codec=str(video_stream.get("codec_name", "")).lower(),
        audio_codec=str(audio_stream.get("codec_name", "")).lower() if audio_stream else None,
    )


def validate_video_for_platforms(meta: VideoMetadata, platforms: set[Platform]) -> list[str]:
    """Trả về danh sách cảnh báo/lỗi kỹ thuật trước khi upload."""
    warnings: list[str] = []

    if Platform.TIKTOK in platforms:
        if meta.size_bytes > 500 * 1024 * 1024:
            warnings.append(
                f"Video nặng {meta.size_bytes / (1024 * 1024):.1f}MB (>500MB, có thể vượt giới hạn khuyến nghị của Zernio/TikTok)."
            )
        if meta.duration_seconds > 600:
            warnings.append(
                f"Video dài {meta.duration_seconds:.1f}s (>10 phút giới hạn TikTok API)."
            )
        if meta.fps and (meta.fps < 23 or meta.fps > 60):
            warnings.append(f"FPS={meta.fps} nằm ngoài dải chuẩn TikTok (23–60 FPS).")
        if meta.video_codec not in ("h264", "hevc", "h265", "vp8", "vp9"):
            warnings.append(f"Codec '{meta.video_codec}' nên chuẩn hóa về H.264 trước khi đăng TikTok.")

    if Platform.YOUTUBE in platforms:
        if not meta.is_youtube_short_eligible:
            warnings.append(
                f"Video ({meta.width}x{meta.height}, {meta.duration_seconds:.1f}s) sẽ được YouTube đăng dạng video thường, không phải Shorts (Shorts cần dọc/vuông và <= 180s)."
            )

    return warnings


def normalize_video_for_shorts_and_tiktok(input_path: Path, output_path: Path) -> Path:
    """
    Chuẩn hóa video gốc thành bản Clean Master chạy mượt trên cả YouTube Shorts & TikTok:
    - 1080x1920 (9:16), giữ tỷ lệ bằng scale+pad không làm méo hình
    - H.264 (yuv420p), 30fps, +faststart
    - AAC 48kHz 128kbps, chuẩn âm lượng -14 LUFS
    """
    ffmpeg_bin = shutil.which("ffmpeg")
    if not ffmpeg_bin:
        raise RuntimeError("Không tìm thấy `ffmpeg` trong PATH.")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    vf = (
        "scale=1080:1920:force_original_aspect_ratio=decrease,"
        "pad=1080:1920:(ow-iw)/2:(oh-ih)/2:color=black,fps=30"
    )
    cmd = [
        ffmpeg_bin,
        "-y",
        "-i",
        str(input_path),
        "-vf",
        vf,
        "-c:v",
        "libx264",
        "-preset",
        "medium",
        "-crf",
        "21",
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "aac",
        "-b:a",
        "128k",
        "-ar",
        "48000",
        "-af",
        "loudnorm=I=-14:TP=-1.5:LRA=11",
        "-movflags",
        "+faststart",
        str(output_path),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"FFmpeg chuẩn hóa thất bại:\n{proc.stderr[-1000:]}")
    return output_path
