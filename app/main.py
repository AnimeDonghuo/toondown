from __future__ import annotations

import asyncio
import logging

from aiohttp import web
from app.config import load_settings
from app.diskutil import free_bytes, human_bytes, total_bytes
from app.tg_client import build_client, start_client
from app.userbot import Worker

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
log = logging.getLogger("toondown")


async def health(_request: web.Request) -> web.Response:
    data_dir = _request.app.get("data_dir", "/tmp/toondown")
    return web.json_response(
        {
            "ok": True,
            "service": "toondown",
            "transport": "mtproto",
            "disk_total": human_bytes(total_bytes(data_dir)),
            "disk_free": human_bytes(free_bytes(data_dir)),
        }
    )


async def amain() -> None:
    settings = load_settings()

    http = web.Application()
    http["data_dir"] = settings.data_dir
    http.router.add_get("/health", health)
    http.router.add_get("/", health)
    runner = web.AppRunner(http)
    await runner.setup()
    site = web.TCPSite(runner, settings.host, settings.port)
    await site.start()
    log.info("health on %s:%s", settings.host, settings.port)

    client = build_client(settings)
    worker = Worker(client, settings)
    await start_client(client, settings)
    await worker.start()
    log.info("MTProto client running")
    await client.run_until_disconnected()


def main() -> None:
    asyncio.run(amain())


if __name__ == "__main__":
    main()
