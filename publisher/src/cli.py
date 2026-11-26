from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path

import typer
from rich.console import Console
from rich.json import JSON
from rich.table import Table

from src.adapters.tiktok_zernio import ZernioTikTokAdapter
from src.adapters.youtube_official import YouTubeOfficialAdapter
from src.config import load_channels, load_settings
from src.db import JobDatabase
from src.media import (
    normalize_video_for_shorts_and_tiktok,
    probe_video,
    validate_video_for_platforms,
)
from src.models import ChannelOverride, Platform, PublishRequest
from src.orchestrator import HybridOrchestrator


app = typer.Typer(help="Hybrid Auto-Publisher CLI: YouTube Official API + TikTok (Zernio / Upload-Post)")
console = Console()


def _parse_datetime(raw: str | None) -> datetime | None:
    if not raw:
        return None
    cleaned = raw.strip().replace(" ", "T")
    return datetime.fromisoformat(cleaned)


@app.command()
def channels(
    config: Path | None = typer.Option(None, "--config", help="Đường dẫn file channels.json"),
) -> None:
    """Hiển thị danh sách 1 YouTube + 2 TikTok đang được cấu hình."""
    settings = load_settings()
    cfg_path = config or settings.channels_config_path
    items = load_channels(cfg_path)

    table = Table(title=f"Configured Channels ({cfg_path})")
    table.add_column("Key", style="cyan")
    table.add_column("Platform", style="magenta")
    table.add_column("Provider", style="green")
    table.add_column("Account / Profile ID")
    table.add_column("Enabled")

    for ch in items:
        ident = (
            ch.account_id
            if ch.provider.value == "zernio"
            else (ch.upload_post_user if ch.provider.value == "upload_post" else str(settings.youtube_token_file.name))
        )
        table.add_row(ch.key, ch.platform.value, ch.provider.value, str(ident or "-"), str(ch.enabled))

    console.print(table)


@app.command("auth-youtube")
def auth_youtube() -> None:
    """Đăng nhập Google OAuth2 Desktop Flow 1 lần để lấy refresh_token cho kênh YouTube."""
    settings = load_settings()
    adapter = YouTubeOfficialAdapter(settings)
    saved = adapter.authenticate_interactive()
    console.print(f"[bold green]Đã lưu YouTube OAuth token thành công tại:[/bold green] {saved}")


@app.command("check-zernio")
def check_zernio() -> None:
    """Kiểm tra ZERNIO_API_KEY và lấy danh sách accountId các kênh TikTok đã kết nối."""
    settings = load_settings()
    adapter = ZernioTikTokAdapter(settings)
    accounts = adapter.list_accounts()

    table = Table(title="Zernio Connected Accounts")
    table.add_column("Account ID", style="cyan")
    table.add_column("Platform", style="magenta")
    table.add_column("Username / Name", style="green")
    table.add_column("Active")

    for acc in accounts:
        acc_id = str(acc.get("_id") or acc.get("id") or "")
        platform = str(acc.get("platform") or "")
        username = str(acc.get("username") or acc.get("displayName") or acc.get("name") or "")
        active = str(acc.get("isActive", True))
        table.add_row(acc_id, platform, username, active)

    console.print(table)


@app.command()
def probe(video: Path = typer.Argument(..., help="Đường dẫn file video cần kiểm tra")) -> None:
    """Kiểm tra thông số kỹ thuật video (độ phân giải, FPS, codec, đủ chuẩn Shorts & TikTok chưa)."""
    meta = probe_video(video)
    warnings = validate_video_for_platforms(meta, {Platform.YOUTUBE, Platform.TIKTOK})

    console.print(JSON.from_data(meta.model_dump(mode="json")))
    console.print(f"Đủ chuẩn YouTube Shorts: [bold]{meta.is_youtube_short_eligible}[/bold]")
    if warnings:
        console.print("[bold yellow]Cảnh báo kỹ thuật:[/bold yellow]")
        for w in warnings:
            console.print(f" - {w}")
    else:
        console.print("[bold green]Video đạt chuẩn kỹ thuật cho cả YouTube Shorts và TikTok![/bold green]")


@app.command()
def normalize(
    input_video: Path = typer.Argument(..., help="Video gốc đầu vào"),
    output_video: Path = typer.Argument(..., help="Đường dẫn video Clean Master đầu ra"),
) -> None:
    """Chuẩn hóa video bằng FFmpeg (1080x1920, H.264, 30fps, AAC -14 LUFS)."""
    out = normalize_video_for_shorts_and_tiktok(input_video, output_video)
    console.print(f"[bold green]Đã chuẩn hóa xong:[/bold green] {out}")


@app.command()
def publish(
    video: Path = typer.Argument(..., help="Đường dẫn file video (.mp4/.mov)"),
    title: str = typer.Option(..., "--title", "-t", help="Tiêu đề YouTube (và caption mặc định TikTok)"),
    description: str = typer.Option("", "--description", "-d", help="Mô tả chi tiết cho YouTube"),
    caption: str | None = typer.Option(None, "--caption", "-c", help="Caption riêng cho TikTok"),
    hashtags: str = typer.Option("", "--hashtags", help="Hashtag cách nhau bằng dấu phẩy, vd: shorts,ai,tiktok"),
    schedule: str | None = typer.Option(
        None,
        "--schedule",
        help="Giờ hẹn đăng (ISO hoặc 'YYYY-MM-DD HH:MM'), bỏ trống = đăng ngay",
    ),
    tiktok2_delay_min: int = typer.Option(
        0,
        "--tiktok2-delay-min",
        help="Đẩy giờ đăng của kênh tiktok_2 trễ thêm N phút so với giờ hẹn (tránh đăng trùng giây)",
    ),
    channels_opt: str | None = typer.Option(
        None,
        "--channels",
        help="Danh sách mã kênh cần đăng cách nhau dấu phẩy (vd: yt_main,tiktok_1,tiktok_2)",
    ),
    thumbnail: Path | None = typer.Option(None, "--thumbnail", help="Ảnh thumbnail tùy chỉnh cho YouTube"),
    ai_content: bool = typer.Option(False, "--ai", help="Bật cờ khai báo nội dung AI (containsSyntheticMedia / is_aigc)"),
    normalize_opt: bool = typer.Option(False, "--normalize", help="Chuẩn hóa FFmpeg trước khi upload"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Chỉ mô phỏng và in payload, KHÔNG gọi API thật"),
    force: bool = typer.Option(False, "--force", help="Bỏ qua kiểm tra chống đăng trùng"),
    config: Path | None = typer.Option(None, "--config", help="Đường dẫn file channels.json"),
) -> None:
    """Đăng hoặc hẹn giờ 1 video lên 1 kênh YouTube + 2 kênh TikTok."""
    settings = load_settings()
    cfg_path = config or settings.channels_config_path
    loaded_channels = load_channels(cfg_path)
    db = JobDatabase(settings.database_path)

    scheduled_dt = _parse_datetime(schedule)
    overrides: dict[str, ChannelOverride] = {}
    if tiktok2_delay_min > 0:
        base_dt = scheduled_dt or datetime.now()
        overrides["tiktok_2"] = ChannelOverride(
            scheduled_at=base_dt + timedelta(minutes=tiktok2_delay_min)
        )

    target_list = [x.strip() for x in channels_opt.split(",") if x.strip()] if channels_opt else None
    tag_list = [x.strip() for x in hashtags.split(",") if x.strip()] if hashtags else []

    req = PublishRequest(
        video_path=video,
        title=title,
        description=description,
        caption=caption,
        hashtags=tag_list,
        thumbnail_path=thumbnail,
        scheduled_at=scheduled_dt,
        timezone=settings.default_timezone,
        is_ai_generated=ai_content,
        target_channels=target_list,
        channel_overrides=overrides,
        normalize_video=normalize_opt,
        dry_run=dry_run,
        force=force,
    )

    orchestrator = HybridOrchestrator(settings, loaded_channels, db)
    results = orchestrator.run(req)

    table = Table(title="Publish Results")
    table.add_column("Channel", style="cyan")
    table.add_column("Provider", style="magenta")
    table.add_column("Status", style="bold")
    table.add_column("Scheduled For")
    table.add_column("Post ID / URL")
    table.add_column("Message")

    for r in results:
        table.add_row(
            r.channel_key,
            r.provider.value,
            r.status.value,
            str(r.scheduled_for or "NOW"),
            str(r.remote_url or r.remote_post_id or "-"),
            r.message,
        )
    console.print(table)

    if dry_run:
        console.print("\n[bold yellow]Chi tiết Payload mô phỏng (--dry-run):[/bold yellow]")
        for r in results:
            console.print(f"\n[cyan]=== {r.channel_key} ({r.provider.value}) ===[/cyan]")
            console.print(JSON.from_data(r.raw_response or {}))


@app.command("publish-manifest")
def publish_manifest(
    manifest: Path = typer.Argument(..., help="File JSON PublishRequest cho phép tùy biến riêng từng kênh"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Chạy mô phỏng"),
    config: Path | None = typer.Option(None, "--config", help="Đường dẫn file channels.json"),
) -> None:
    """Đăng bài từ file manifest JSON (tùy biến riêng title/caption/giờ đăng cho cả 3 kênh)."""
    settings = load_settings()
    cfg_path = config or settings.channels_config_path
    loaded_channels = load_channels(cfg_path)
    db = JobDatabase(settings.database_path)

    data = json.loads(manifest.read_text(encoding="utf-8"))
    if dry_run:
        data["dry_run"] = True
    req = PublishRequest.model_validate(data)

    orchestrator = HybridOrchestrator(settings, loaded_channels, db)
    results = orchestrator.run(req)
    for r in results:
        console.print(f"[{r.status.value}] {r.channel_key} ({r.provider.value}) -> {r.remote_url or r.remote_post_id or r.message}")


@app.command()
def history(limit: int = typer.Option(20, "--limit", "-n", help="Số bản ghi gần nhất")) -> None:
    """Xem lịch sử các job đăng bài trong SQLite."""
    settings = load_settings()
    db = JobDatabase(settings.database_path)
    rows = db.list_recent(limit=limit)

    table = Table(title=f"Recent Publish Jobs (last {limit})")
    table.add_column("ID")
    table.add_column("Channel", style="cyan")
    table.add_column("Provider")
    table.add_column("Status", style="bold")
    table.add_column("Scheduled")
    table.add_column("Remote ID / URL")
    table.add_column("Updated At")

    for row in rows:
        table.add_row(
            str(row["id"]),
            str(row["channel_key"]),
            str(row["provider"]),
            str(row["status"]),
            str(row["scheduled_for"] or "NOW"),
            str(row["remote_url"] or row["remote_post_id"] or row["error_message"] or "-"),
            str(row["updated_at"]),
        )
    console.print(table)


if __name__ == "__main__":
    app()
