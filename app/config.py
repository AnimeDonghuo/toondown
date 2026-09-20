from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


def _int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    return int(raw)


def _csv_ints(name: str) -> frozenset[int]:
    raw = os.getenv(name, "")
    out: set[int] = set()
    for part in raw.split(","):
        part = part.strip()
        if part:
            out.add(int(part))
    return frozenset(out)


@dataclass(frozen=True)
class Settings:
    bot_token: str
    webhook_secret: str
    public_url: str
    allowed_user_ids: frozenset[int]
    bili_sessdata: str
    bili_jct: str
    bili_dedeuserid: str
    bili_tid: int
    bili_tags: str
    bili_copyright: int
    max_file_mb: int
    port: int
    host: str

    @property
    def bili_ready(self) -> bool:
        return bool(self.bili_sessdata and self.bili_jct)

    @property
    def webhook_path(self) -> str:
        return f"/tg/{self.webhook_secret}"

    @property
    def webhook_url(self) -> str:
        return f"{self.public_url}{self.webhook_path}"


def load_settings() -> Settings:
    token = os.getenv("BOT_TOKEN", "").strip()
    secret = os.getenv("WEBHOOK_SECRET", "").strip()
    public = os.getenv("PUBLIC_URL", "").strip().rstrip("/")
    if not token:
        raise SystemExit("BOT_TOKEN is required")
    if not secret:
        raise SystemExit("WEBHOOK_SECRET is required")
    if not public.startswith("https://"):
        raise SystemExit("PUBLIC_URL must be an https:// origin (Koyeb app URL)")

    return Settings(
        bot_token=token,
        webhook_secret=secret,
        public_url=public,
        allowed_user_ids=_csv_ints("ALLOWED_USER_IDS"),
        bili_sessdata=os.getenv("BILI_SESSDATA", "").strip(),
        bili_jct=os.getenv("BILI_JCT", "").strip(),
        bili_dedeuserid=os.getenv("BILI_DEDEUSERID", "").strip(),
        bili_tid=_int("BILI_TID", 122),
        bili_tags=os.getenv("BILI_TAGS", "toondown").strip() or "toondown",
        bili_copyright=_int("BILI_COPYRIGHT", 1),
        max_file_mb=_int("MAX_FILE_MB", 19),
        port=_int("PORT", 8000),
        host=os.getenv("HOST", "0.0.0.0"),
    )
