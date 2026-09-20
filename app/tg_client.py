"""Build a Telethon client.

api_id + api_hash only name the app. Telegram still needs a login:

- user phone login → a session (string OR toondown.session file) → 2 GB files
- bot token → still a bot → 20 MB downloads (Telegram server limit, not this repo)

There is no 2 GB path that is only api_id and api_hash.
"""

from __future__ import annotations

import logging
from pathlib import Path

from telethon import TelegramClient
from telethon.sessions import StringSession

from app.config import Settings

log = logging.getLogger("toondown.tg")


def build_client(settings: Settings) -> TelegramClient:
    kwargs = dict(
        api_id=settings.api_id,
        api_hash=settings.api_hash,
        device_model="toondown",
        system_version="Koyeb",
        app_version="2.0",
        sequential_updates=True,
    )
    if settings.session:
        log.info("auth: StringSession (user account, 2 GB class)")
        return TelegramClient(StringSession(settings.session), **kwargs)
    if settings.bot_token:
        log.warning(
            "auth: bot token — Telegram bots cannot download more than ~20 MB"
        )
        return TelegramClient("toondown-bot", **kwargs)
    path = Path(settings.session_name + ".session")
    log.info("auth: session file %s (must already exist on the server)", path)
    return TelegramClient(settings.session_name, **kwargs)


async def start_client(client: TelegramClient, settings: Settings) -> None:
    if settings.bot_token and not settings.session:
        await client.start(bot_token=settings.bot_token)
        return
    await client.start()
    if not await client.is_user_authorized():
        raise SystemExit(
            "Not logged in. api_id/api_hash are not enough. On your PC run:\n"
            "  python -m app.login\n"
            "then set TELEGRAM_SESSION to the printed string, or copy "
            "toondown.session next to the app."
        )
