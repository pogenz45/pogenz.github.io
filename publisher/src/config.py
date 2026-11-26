from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

from src.models import ChannelConfig


BASE_DIR = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class AppSettings:
    base_dir: Path
    default_timezone: str
    channels_config_path: Path
    database_path: Path

    youtube_client_secrets_file: Path
    youtube_token_file: Path

    zernio_api_key: str
    zernio_base_url: str

    upload_post_api_key: str
    upload_post_base_url: str


def _resolve_path(raw: str, base_dir: Path) -> Path:
    p = Path(raw)
    return p if p.is_absolute() else (base_dir / p)


def load_settings(env_file: Path | None = None) -> AppSettings:
    """Đọc biến môi trường từ .env (nếu có) và trả về AppSettings."""
    target_env = env_file or (BASE_DIR / ".env")
    if target_env.exists():
        load_dotenv(target_env, override=False)

    return AppSettings(
        base_dir=BASE_DIR,
        default_timezone=os.getenv("DEFAULT_TIMEZONE", "Asia/Ho_Chi_Minh"),
        channels_config_path=_resolve_path(
            os.getenv("CHANNELS_CONFIG_PATH", "config/channels.json"), BASE_DIR
        ),
        database_path=_resolve_path(
            os.getenv("DATABASE_PATH", "data/publisher.db"), BASE_DIR
        ),
        youtube_client_secrets_file=_resolve_path(
            os.getenv("YOUTUBE_CLIENT_SECRETS_FILE", ".secrets/youtube_client_secret.json"),
            BASE_DIR,
        ),
        youtube_token_file=_resolve_path(
            os.getenv("YOUTUBE_TOKEN_FILE", ".secrets/youtube_token.json"),
            BASE_DIR,
        ),
        zernio_api_key=os.getenv("ZERNIO_API_KEY", "").strip(),
        zernio_base_url=os.getenv("ZERNIO_BASE_URL", "https://zernio.com/api/v1").rstrip("/"),
        upload_post_api_key=os.getenv("UPLOAD_POST_API_KEY", "").strip(),
        upload_post_base_url=os.getenv("UPLOAD_POST_BASE_URL", "https://api.upload-post.com").rstrip("/"),
    )


def load_channels(config_path: Path) -> list[ChannelConfig]:
    """Đọc danh sách kênh từ channels.json (fallback về channels.example.json nếu truyền tường minh)."""
    if not config_path.exists():
        raise FileNotFoundError(
            f"Không tìm thấy file cấu hình kênh tại: {config_path}. "
            f"Hãy copy `config/channels.example.json` sang `config/channels.json` và điền ID kênh."
        )
    raw_data = json.loads(config_path.read_text(encoding="utf-8"))
    items = raw_data.get("channels", [])
    channels = [ChannelConfig.model_validate(item) for item in items]

    seen: set[str] = set()
    for ch in channels:
        if ch.key in seen:
            raise ValueError(f"Trùng mã kênh '{ch.key}' trong {config_path}")
        seen.add(ch.key)
    return channels
