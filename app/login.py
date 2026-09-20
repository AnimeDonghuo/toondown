"""One-time PC login. api_id + api_hash are not enough by themselves.

  TELEGRAM_API_ID=... TELEGRAM_API_HASH=... python -m app.login
"""

from __future__ import annotations

import asyncio
import os
import sys

from dotenv import load_dotenv
from telethon import TelegramClient
from telethon.sessions import StringSession


async def _run() -> None:
    load_dotenv()
    api_id = os.getenv("TELEGRAM_API_ID", "").strip()
    api_hash = os.getenv("TELEGRAM_API_HASH", "").strip()
    if not api_id or not api_hash:
        sys.exit("Set TELEGRAM_API_ID and TELEGRAM_API_HASH (from https://my.telegram.org)")

    client = TelegramClient(StringSession(), int(api_id), api_hash)
    await client.start()
    me = await client.get_me()
    session = client.session.save()
    print()
    print(f"logged in as {me.username or me.first_name} id={me.id}")
    print()
    print("That login is stored as TELEGRAM_SESSION (paste one line into .env / Koyeb):")
    print()
    print(session)
    print()
    print("api_id + api_hash only identify the app. The string above is the user login.")
    print("Without it (or a toondown.session file), Telegram will not give you 2 GB files.")
    print()
    await client.disconnect()


def main() -> None:
    asyncio.run(_run())


if __name__ == "__main__":
    main()
