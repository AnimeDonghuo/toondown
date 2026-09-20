from __future__ import annotations

import logging

from aiohttp import web
from aiogram import Bot
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application

from app.bot import build_dispatcher
from app.config import Settings, load_settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
log = logging.getLogger("toondown")


async def on_startup(bot: Bot, settings: Settings) -> None:
    await bot.set_webhook(settings.webhook_url, drop_pending_updates=True)
    log.info("webhook set to %s", settings.webhook_url)


async def on_shutdown(bot: Bot) -> None:
    await bot.delete_webhook()


async def health(_request: web.Request) -> web.Response:
    return web.json_response({"ok": True, "service": "toondown"})


def main() -> None:
    settings = load_settings()
    bot = Bot(settings.bot_token)
    dp = build_dispatcher(settings)
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)

    app = web.Application()
    app["settings"] = settings
    app.router.add_get("/health", health)
    app.router.add_get("/", health)
    SimpleRequestHandler(dispatcher=dp, bot=bot).register(
        app, path=settings.webhook_path
    )
    setup_application(app, dp, bot=bot, settings=settings)
    web.run_app(app, host=settings.host, port=settings.port)


if __name__ == "__main__":
    main()
