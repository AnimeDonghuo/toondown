# toondown

Telegram bot you can park on **Koyeb’s free instance**. It accepts a video you send in chat and, if you configure mainland Bilibili cookies, publishes it through `member.bilibili.com`.

It will **not** upload to the 2026 international Bilibili app. That app has no public upload API.

## Can I pipe Telegram → international Bilibili?

**No official API, and no web studio yet.**

The global Android app (pink icon, globe in the corner, shipped August 2026 by BILIBILI SINGAPORE PTE. LTD.) lets people sign up without passport KYC and upload from the phone. Public statements from [@bilibili_create](https://x.com/bilibili_create) still list:

- Android only (iOS “coming soon”)
- English website / creator studio “coming soon”
- onboarding via their Discord, plus a certificate quiz before posting

There is no documented creator REST API, no OAuth app, and no desktop uploader for that product. Community tools such as [biliup](https://github.com/biliup/biliup) talk to **mainland** `bilibili.com`, which is a different account system and still expects real-name verification for most uploads.

Phone uploads feel slow because the file has to leave the phone’s radio. A Koyeb Nano does not fix that:

| Limit | Reality |
| --- | --- |
| Telegram Bot API `getFile` | **20 MB** download. Need a self-hosted Bot API server (or a user account / Telethon) for 2 GB. |
| Koyeb free instance | 512 MB RAM, ~2 GB disk, **no volume**, sleeps after ~1 hour idle. Cannot hold a long HD file. |
| Intl app upload cap (reports) | around **2 GB**, app-only |

If the video is already “too slow on the phone”, it is already too big for this free-tier bot.

### What actually works today

1. **International app, faster than phone**  
   Copy the file to a PC (USB, SMB, Drive). Run an Android emulator (or a spare Android device on Ethernet/Wi‑Fi 6) and upload from there. Same app, wired uplink.
2. **Mainland bilibili.com**  
   Browser studio at [member.bilibili.com](https://member.bilibili.com/) — this is what the bot automates with cookies. Account usually needs 实名认证. Use only for content you have the rights to publish.
3. **Wait for the English web studio**  
   That is the path that will eventually replace phone uploads for international creators.

Do not use this to re-upload other people’s anime, donghua, or any unlicensed catalog.

## Run it

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # fill BOT_TOKEN, WEBHOOK_SECRET, PUBLIC_URL, ALLOWED_USER_IDS
python -m app.main
```

Create the bot with [@BotFather](https://t.me/BotFather). Send `/whoami` to the bot, then put that id in `ALLOWED_USER_IDS`.

### Koyeb (free web service)

1. Push this repo, **Web Service** from GitHub, Frankfurt or Washington.
2. Instance: **Free** (Nano). HTTP port `8000`.
3. Environment:

   | Key | Value |
   | --- | --- |
   | `BOT_TOKEN` | from BotFather |
   | `WEBHOOK_SECRET` | long random string |
   | `PUBLIC_URL` | `https://<your-app>.koyeb.app` (no trailing slash) |
   | `ALLOWED_USER_IDS` | your Telegram user id |
   | `BILI_SESSDATA` / `BILI_JCT` / `BILI_DEDEUSERID` | optional, mainland cookies |
   | `BILI_TID` | partition, default `122` |
   | `PORT` | `8000` if you override the probe |

4. Health path: `/health`. After deploy, `/start` the bot. First message after idle may wait for a cold start.

Koyeb free **scales to zero**. Webhook is required; polling dies when the instance sleeps.

### Mainland cookies (optional)

Logged in at `member.bilibili.com`, DevTools → Application → Cookies:

- `SESSDATA`
- `bili_jct`
- `DedeUserID`

Treat them as a password. They expire. This bot never logs cookie values.

Caption when you send a video:

```
My title
tag1,tag2,tag3
description text
source: https://example.com/original   # only for reprints
```

## Why not reverse the international app?

Private mobile endpoints are unpublished, change without notice, and tying a bot to them is brittle and against typical app ToS. When Bilibili ships the English web uploader, that is the thing to wire up — not a scraped Android protobuf.

## License

Use at your own risk. You are responsible for what you publish and for keeping cookies private.
