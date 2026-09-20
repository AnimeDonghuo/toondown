# toondown

Pull a video from Telegram (or a direct URL) and optionally publish it to **mainland** bilibili.com.

## FAQ

### I only have api_id and api_hash. That is enough for 2 GB, right?

**No.** `api_id` / `api_hash` from [my.telegram.org](https://my.telegram.org) only name your *app*. Telegram still asks “who are you?”

| What you have | What Telegram allows |
| --- | --- |
| api_id + api_hash only | Nothing. Not logged in. |
| api_id + api_hash + **phone login** (this becomes `TELEGRAM_SESSION` or `toondown.session`) | Same as the official app: **2 GB** (4 GB Premium) |
| api_id + api_hash + **BotFather token** | Still a **bot**. Download cap **~20 MB**. MTProto does not remove that. |

The “session” is not extra bureaucracy. It **is** the phone login. Tutorials that “only use api_id and hash” still create a `something.session` file the first time you type your number. On Koyeb there is no keyboard, so you do that login once on a PC (`python -m app.login`) and paste the printed string into `TELEGRAM_SESSION`.

### What is `BILI_SESSDATA` and `bili_jct`?

They are **website cookies** for **mainland** [bilibili.com](https://www.bilibili.com) / [member.bilibili.com](https://member.bilibili.com) (the Chinese studio). They are the site’s “you are logged in” tickets.

| Cookie | What it is |
| --- | --- |
| `SESSDATA` | Login ticket |
| `bili_jct` | CSRF token (must match the same login) |
| `DedeUserID` | Your numeric uid (optional but useful) |

**How to copy them (mainland web only):**

1. On a computer, open Chrome/Firefox.
2. Log in at https://member.bilibili.com (the upload studio).
3. F12 → **Application** (Chrome) or **Storage** (Firefox) → **Cookies** → `https://www.bilibili.com` or `https://member.bilibili.com`.
4. Copy the values of `SESSDATA` and `bili_jct` into Koyeb env. Treat them like a password. They expire.

### How do I get those from Bilibili **International** (pink icon + globe)?

**You don’t.** The international app does not use `SESSDATA` / `bili_jct`. Those names exist on the **Chinese website**, not in the 2026 global Android app.

The international app has:

- no public upload API
- no English web studio yet
- no documented cookies this uploader can send

An account you made only inside the international app will **not** give you `SESSDATA` for `member.bilibili.com`. Mainland upload also usually wants 实名认证 (real-name check). Different product.

For the international app the only practical “remote” path in this repo is: download the file with Telegram (user session), then on a **PC** `ADB_ENABLED=1` so it lands in the emulator/phone Download folder, and you tap Upload in the app.

## Remote video from Telegram

User session (not Bot API):

| You send | What happens |
| --- | --- |
| Video / file / forward | MTProto download, 2 GB / 4 GB |
| `https://t.me/channel/123` or `/dl <t.me link>` | Fetch that message if this account can see it |
| `https://host/file.mp4` | Direct HTTP file |

`/status` shows real disk. Cap = `min(MAX_FILE_MB, free − 400 MB)`.

## Koyeb

Official free instance: 512 MB RAM, 0.1 vCPU, **2 GB SSD**. Code uses whatever disk is actually free (`/status`). Ping `/health` or it sleeps.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# fill TELEGRAM_API_ID / TELEGRAM_API_HASH
python -m app.login          # once, on a PC, phone code
# paste TELEGRAM_SESSION into .env
python -m app.main
```

Only publish content you have the rights to.
