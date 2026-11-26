from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.models import JobStatus, Platform, Provider


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS publish_jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    idempotency_key TEXT NOT NULL UNIQUE,
    channel_key TEXT NOT NULL,
    platform TEXT NOT NULL,
    provider TEXT NOT NULL,
    video_path TEXT NOT NULL,
    video_sha256 TEXT NOT NULL,
    title TEXT NOT NULL,
    scheduled_for TEXT,
    status TEXT NOT NULL,
    remote_post_id TEXT,
    remote_url TEXT,
    error_message TEXT,
    raw_response_json TEXT,
    attempts INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_publish_jobs_channel_status
    ON publish_jobs(channel_key, status);
"""


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def compute_file_sha256(file_path: Path, chunk_size: int = 1024 * 1024) -> str:
    hasher = hashlib.sha256()
    with file_path.open("rb") as fh:
        while True:
            chunk = fh.read(chunk_size)
            if not chunk:
                break
            hasher.update(chunk)
    return hasher.hexdigest()


def build_idempotency_key(video_sha256: str, channel_key: str, scheduled_for: str | None) -> str:
    raw = f"{video_sha256}:{channel_key}:{scheduled_for or 'NOW'}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]


class JobDatabase:
    """SQLite storage quản lý trạng thái đăng bài & chống đăng trùng (idempotency)."""

    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.executescript(SCHEMA_SQL)

    def get_by_idempotency_key(self, key: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM publish_jobs WHERE idempotency_key = ?",
                (key,),
            ).fetchone()
            return dict(row) if row else None

    def upsert_job_start(
        self,
        *,
        idempotency_key: str,
        channel_key: str,
        platform: Platform,
        provider: Provider,
        video_path: Path,
        video_sha256: str,
        title: str,
        scheduled_for: str | None,
    ) -> None:
        now = utc_now_iso()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO publish_jobs (
                    idempotency_key, channel_key, platform, provider,
                    video_path, video_sha256, title, scheduled_for,
                    status, attempts, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?)
                ON CONFLICT(idempotency_key) DO UPDATE SET
                    status = excluded.status,
                    attempts = publish_jobs.attempts + 1,
                    error_message = NULL,
                    updated_at = excluded.updated_at
                """,
                (
                    idempotency_key,
                    channel_key,
                    platform.value,
                    provider.value,
                    str(video_path),
                    video_sha256,
                    title,
                    scheduled_for,
                    JobStatus.RUNNING.value,
                    now,
                    now,
                ),
            )

    def mark_success(
        self,
        *,
        idempotency_key: str,
        remote_post_id: str | None,
        remote_url: str | None,
        raw_response: dict[str, Any] | None,
    ) -> None:
        now = utc_now_iso()
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE publish_jobs
                SET status = ?,
                    remote_post_id = ?,
                    remote_url = ?,
                    error_message = NULL,
                    raw_response_json = ?,
                    updated_at = ?
                WHERE idempotency_key = ?
                """,
                (
                    JobStatus.SUCCESS.value,
                    remote_post_id,
                    remote_url,
                    json.dumps(raw_response, ensure_ascii=False) if raw_response is not None else None,
                    now,
                    idempotency_key,
                ),
            )

    def mark_failed(
        self,
        *,
        idempotency_key: str,
        error_message: str,
        raw_response: dict[str, Any] | None = None,
    ) -> None:
        now = utc_now_iso()
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE publish_jobs
                SET status = ?,
                    error_message = ?,
                    raw_response_json = COALESCE(?, raw_response_json),
                    updated_at = ?
                WHERE idempotency_key = ?
                """,
                (
                    JobStatus.FAILED.value,
                    error_message,
                    json.dumps(raw_response, ensure_ascii=False) if raw_response is not None else None,
                    now,
                    idempotency_key,
                ),
            )

    def list_recent(self, limit: int = 20) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM publish_jobs ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
            return [dict(r) for r in rows]
