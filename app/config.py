from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

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


def _bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    api_id: int
    api_hash: str
    session: str
    session_name: str
    bot_token: str
    allowed_user_ids: frozenset[int]
    bili_sessdata: str
    bili_jct: str
    bili_dedeuserid: str
    bili_tid: int
    bili_tags: str
    bili_copyright: int
    max_file_mb: int
    data_dir: str
    adb_enabled: bool
    adb_bin: str
    adb_serial: str
    adb_remote_dir: str
    port: int
    host: str

    @property
    def bili_ready(self) -> bool:
        return bool(self.bili_sessdata and self.bili_jct)

    @property
    def telegram_ready(self) -> bool:
        return bool(self.session or self.bot_token or Path(self.session_name + ".session").exists())


def load_settings() -> Settings:
    api_id_raw = os.getenv("TELEGRAM_API_ID", "").strip()
    api_hash = os.getenv("TELEGRAM_API_HASH", "").strip()
    session = os.getenv("TELEGRAM_SESSION", "").strip()
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    session_name = os.getenv("TELEGRAM_SESSION_NAME", "toondown").strip() or "toondown"
    if not api_id_raw or not api_hash:
        raise SystemExit("TELEGRAM_API_ID and TELEGRAM_API_HASH are required (my.telegram.org)")
    if not session and not bot_token and not Path(session_name + ".session").exists():
        raise SystemExit(
            "api_id + api_hash are not a login.\n"
            "For 2 GB files you need a USER login: run  python -m app.login  and set TELEGRAM_SESSION\n"
            "  (or copy toondown.session here).\n"
            "A BotFather token (TELEGRAM_BOT_TOKEN) only does ~20 MB."
        )

    return Settings(
        api_id=int(api_id_raw),
        api_hash=api_hash,
        session=session,
        session_name=session_name,
        bot_token=bot_token,
        allowed_user_ids=_csv_ints("ALLOWED_USER_IDS"),
        bili_sessdata=os.getenv("BILI_SESSDATA", "").strip(),
        bili_jct=os.getenv("BILI_JCT", "").strip(),
        bili_dedeuserid=os.getenv("BILI_DEDEUSERID", "").strip(),
        bili_tid=_int("BILI_TID", 122),
        bili_tags=os.getenv("BILI_TAGS", "toondown").strip() or "toondown",
        bili_copyright=_int("BILI_COPYRIGHT", 1),
        max_file_mb=_int("MAX_FILE_MB", 16000),
        data_dir=os.getenv("DATA_DIR", "/tmp/toondown").strip() or "/tmp/toondown",
        adb_enabled=_bool("ADB_ENABLED", False),
        adb_bin=os.getenv("ADB_BIN", "adb").strip() or "adb",
        adb_serial=os.getenv("ADB_SERIAL", "").strip(),
        adb_remote_dir=os.getenv("ADB_REMOTE_DIR", "/sdcard/Download/toondown").strip()
        or "/sdcard/Download/toondown",
        port=_int("PORT", 8000),
        host=os.getenv("HOST", "0.0.0.0"),
    )
