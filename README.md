# toondown

Telegram **user client** (MTProto, `api_id` / `api_hash`) that:

1. Pulls videos up to **2 GB** (4 GB with Telegram Premium) — not the Bot API 20 MB cap.
2. Optionally publishes them to **mainland** `member.bilibili.com` with studio cookies.
3. Optionally `adb push`es them into an Android emulator/device **Download** folder so you can tap Upload in the international Bilibili app on a PC.

It does **not** reverse-engineer the 2026 international Bilibili app, and it does **not** run that emulator on Koyeb’s free instance.

## What I will not build

| Ask | Why not |
| --- | --- |
| Unofficial API scraped from the intl APK | Private mobile endpoints, unpublished, ToS, and they move. This repo will not MITM or decompile that app. |
| Android emulator on Koyeb free | Free Nano is **512 MB RAM, 0.1 vCPU, ~2 GB disk, no KVM**. An emulator wants several GB and hardware virtualization. |

## Telegram 20 MB bypass (this is real)

BotFather bots use HTTP Bot API: `getFile` max **20 MB**.

A **user account** uses MTProto with the api_id/api_hash from [my.telegram.org](https://my.telegram.org). Same limits as the official app: **2 GB** free, **4 GB** Premium.

That is Telethon in this repo. You log in once on your machine, copy `TELEGRAM_SESSION` to Koyeb, and send (or forward) a video to that account.

Koyeb free **disk** is still ~2 GB for the whole container, so a 1.5 GB file may not fit even though Telegram would allow it. `/status` prints free disk. For long HD videos, run the same process on a PC.

Koyeb free also **sleeps after ~1 hour with no HTTP**. MTProto is not HTTP. Ping `https://<app>.koyeb.app/health` every few minutes (UptimeRobot or similar) or the client dies.

## International app: emulator on a PC (not Koyeb)

Fastest path that exists today:

1. Run this repo **on your computer** (or any box with disk + a GPU/CPU that can virtualize).
2. Start Android emulator or plug in a phone over USB. Install the pink-globe Bilibili app. `adb devices` must see it.
3. `ADB_ENABLED=1` in `.env`.
4. Forward a video to the Telegram account this client is logged in as.
5. The file lands in `/sdcard/Download/toondown/`. Open Bilibili → Upload. Use Ethernet/Wi‑Fi 6, not phone LTE.

That is not an API. It is “get the file onto the device without using the phone’s radio for the Telegram hop.”

Mainland studio (different product, often needs 实名认证): set `BILI_SESSDATA` / `BILI_JCT`.

Only upload content you have the rights to publish.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

1. Open https://my.telegram.org → API development tools → create an app. Put `TELEGRAM_API_ID` and `TELEGRAM_API_HASH` in `.env`.
2. Login once (phone code, local only):

```bash
python -m app.login
```

3. Paste the printed string into `TELEGRAM_SESSION`.
4. `ALLOWED_USER_IDS` — your Telegram id, or leave empty to only accept the logged-in account (Saved Messages works).

```bash
python -m app.main
```

Send `/help` or a video to that account.

### Koyeb free web service

Dockerfile is included. HTTP port **8000**, health `/health`.

Env: `TELEGRAM_API_ID`, `TELEGRAM_API_HASH`, `TELEGRAM_SESSION`, optional Bilibili cookies, `PORT=8000`.

Do not enable ADB on Koyeb. Do not expect 2 GB files to fit.

### Caption

```
Title
tag1,tag2
description
source: https://original   # reprints only
```

## License

Use at your own risk. Session strings and cookies are passwords.
