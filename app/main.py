from __future__ import annotations

import asyncio
import logging

from aiohttp import web
from telethon import TelegramClient
from telethon.sessions import StringSession

from app.config import load_settings
from app.userbot import Worker

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
log = logging.getLogger("toondown")


async def health(_request: web.Request) -> web.Response:
    return web.json_response({"ok": True, "service": "toondown", "transport": "mtproto"})


async def amain() -> None:
    settings = load_settings()

    http = web.Application()
    http.router.add_get("/health", health)
    http.router.add_get("/", health)
    runner = web.AppRunner(http)
    await runner.setup()
    site = web.TCPSite(runner, settings.host, settings.port)
    await site.start()
    log.info("health on %s:%s", settings.host, settings.port)

    client = TelegramClient(
        StringSession(settings.session),
        settings.api_id,
        settings.api_hash,
        device_model="toondown",
        system_version="Koyeb",
        app_version="2.0",
        sequential_updates=True,
    )
    worker = Worker(client, settings)
    await client.start()
    await worker.start()
    log.info("MTProto client running")
    await client.run_until_disconnected()


def main() -> None:
    asyncio.run(amain())


if __name__ == "__main__":
    main()
