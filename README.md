# toondown

Telegram **user client** (MTProto, `api_id` / `api_hash`). It pulls a video that already lives in Telegram — or a remote URL you paste — and can publish it to mainland `member.bilibili.com`.

## Remote video from Telegram

The 20 MB Bot API cap does **not** apply. This process is a user account:

| You send | What happens |
| --- | --- |
| Video / file / forward | Downloaded over MTProto (2 GB, or 4 GB Premium) |
| `https://t.me/channel/123` or `https://t.me/c/…/123` | Same account fetches that message if it can see it |
| `https://host/file.mp4` or `/dl <url>` | Direct HTTP file, streamed to disk |
| Caption around the link | Title / tags / description (see below) |

`/status` prints **real disk total and free**. Jobs are capped to `min(MAX_FILE_MB, free − 400 MB)`.

## Koyeb storage

Current Koyeb docs: the **free instance** is 512 MB RAM, 0.1 vCPU, **2 GB SSD**, no attached volume, sleeps after ~1 hour without HTTP.

If your dashboard really shows ~18 GB ephemeral (older/paid nano, or a different product), this code does not hard-code 2 GB. It uses `shutil.disk_usage` on `DATA_DIR`. Send `/status` after deploy and believe that number.

RAM is still **512 MB** on free. Downloads and Bilibili uploads are chunked so a multi-GB file does not have to fit in memory — only on disk.

Ping `/health` every few minutes or the instance sleeps and the MTProto client dies.

## What this will not do

- Reverse the 2026 international Bilibili app
- Run an Android emulator on Koyeb Nano
- yt-dlp / YouTube / random site ripping (send a **direct file** or a Telegram message)

Intl app on a **PC**: `ADB_ENABLED=1`, file lands in `/sdcard/Download/toondown/`, you tap Upload.

Only publish content you have the rights to.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

1. [my.telegram.org](https://my.telegram.org) → `TELEGRAM_API_ID` / `TELEGRAM_API_HASH`
2. `python -m app.login` → paste `TELEGRAM_SESSION`
3. Optional mainland cookies: `BILI_SESSDATA`, `BILI_JCT`
4. `python -m app.main`

Then in a private chat with that account:

```
/status
/dl https://t.me/yourchannel/15
```

or forward the video, or paste:

```
Episode title
tag1,tag2
https://cdn.example.com/mine.mp4
source: https://original
```

### Koyeb

Web service, Dockerfile, port `8000`, health `/health`.

Env: `TELEGRAM_API_ID`, `TELEGRAM_API_HASH`, `TELEGRAM_SESSION`, optional Bilibili cookies, `DATA_DIR=/tmp/toondown`, `MAX_FILE_MB=16000`.

## License

Use at your own risk. Session strings and cookies are passwords.
