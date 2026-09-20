from __future__ import annotations

import asyncio
import logging
import os
import tempfile
import time
from pathlib import Path

from telethon import TelegramClient, events
from telethon.tl.custom import Message

from app.adb_push import AdbError, push_file
from app.bili_upload import BiliError, BiliWebUploader, parse_caption
from app.config import Settings
from app.diskutil import free_bytes, max_file_bytes

log = logging.getLogger("toondown.userbot")

HELP = (
    "MTProto user client (api_id / api_hash). Telegram Bot API 20 MB limit "
    "does not apply — free accounts can send 2 GB, Premium 4 GB.\n\n"
    "Send a video or file. Caption:\n"
    "  Title\n"
    "  tag1,tag2\n"
    "  description\n"
    "  source: https://...   (reprint only)\n\n"
    "Commands: /help  /whoami  /status\n\n"
    "International Bilibili app: no public API. This process will not "
    "reverse that app. On a PC with an emulator, enable ADB_ENABLED to "
    "adb-push into Download/, then tap Upload in the app on wired internet.\n"
    "Mainland member.bilibili.com: set SESSDATA cookies.\n"
    "Only publish content you have rights to."
)


def _name_of(msg: Message) -> str:
    if msg.file and msg.file.name:
        return msg.file.name.replace("/", "_")
    if msg.video:
        return "video.mp4"
    if msg.gif:
        return "anim.mp4"
    return "file.bin"


def _size_of(msg: Message) -> int:
    if msg.file and msg.file.size:
        return int(msg.file.size)
    return 0


class Worker:
    def __init__(self, client: TelegramClient, settings: Settings) -> None:
        self.client = client
        self.settings = settings
        self.lock = asyncio.Lock()
        self.allowed: set[int] = set(settings.allowed_user_ids)
        self.self_id = 0

    async def start(self) -> None:
        me = await self.client.get_me()
        self.self_id = int(me.id)
        self.allowed.add(self.self_id)
        log.info("logged in as id=%s username=%s", me.id, me.username)

        @self.client.on(events.NewMessage(incoming=True, outgoing=True))
        async def _on_msg(event: events.NewMessage.Event) -> None:
            await self.on_message(event)

    def _ok_user(self, msg: Message) -> bool:
        sender = msg.sender_id
        return sender is not None and int(sender) in self.allowed

    async def on_message(self, event: events.NewMessage.Event) -> None:
        msg: Message = event.message
        if not event.is_private:
            return
        if not self._ok_user(msg):
            return
        text = (msg.raw_text or "").strip()
        if text.startswith("/whoami"):
            await event.reply(f"your id: {msg.sender_id}\nself id: {self.self_id}")
            return
        if text.startswith("/help") or text.startswith("/start"):
            await event.reply(HELP)
            return
        if text.startswith("/status"):
            await event.reply(await self.status_text())
            return
        if not (msg.video or msg.document or msg.gif):
            if text and not text.startswith("/"):
                await event.reply("Send a video/file, or /help.")
            return
        await self.handle_media(event)

    async def status_text(self) -> str:
        s = self.settings
        lines = [
            "transport: MTProto (Telethon user account)",
            f"max file cfg: {s.max_file_mb} MB",
            f"free disk: {free_bytes('/tmp') / 1024 / 1024:.0f} MB",
            f"usable now: {max_file_bytes(s.max_file_mb) / 1024 / 1024:.0f} MB",
            f"mainland cookies: {'yes' if s.bili_ready else 'NO'}",
            f"adb push: {'on' if s.adb_enabled else 'off'}",
            "intl app API: none (will not reverse the APK)",
        ]
        if s.bili_ready:
            try:
                async with BiliWebUploader(
                    s.bili_sessdata, s.bili_jct, s.bili_dedeuserid
                ) as bili:
                    me = await bili.whoami()
                lines.append(f"bilibili: {me.get('uname')} mid={me.get('mid')}")
            except Exception as exc:  # noqa: BLE001
                lines.append(f"bilibili login FAILED: {exc}")
        return "\n".join(lines)

    async def handle_media(self, event: events.NewMessage.Event) -> None:
        if self.lock.locked():
            await event.reply("Busy with another file. Send again in a minute.")
            return

        msg: Message = event.message
        name = _name_of(msg)
        size = _size_of(msg)
        cap = max_file_bytes(self.settings.max_file_mb)
        if size and size > cap:
            await event.reply(
                f"{name} is {size / 1024 / 1024:.1f} MB. "
                f"This host can take {cap / 1024 / 1024:.0f} MB "
                f"(MAX_FILE_MB + free disk). Koyeb free disk is ~2 GB total."
            )
            return

        if not self.settings.bili_ready and not self.settings.adb_enabled:
            await event.reply(
                "No destination configured.\n"
                "- mainland: set BILI_SESSDATA + BILI_JCT\n"
                "- intl app: run this on a PC with an emulator, ADB_ENABLED=1\n"
                "There is no unofficial intl upload API in this project."
            )
            return

        async with self.lock:
            await self._run_job(event, name, size)

    async def _run_job(
        self, event: events.NewMessage.Event, name: str, size: int
    ) -> None:
        msg: Message = event.message
        meta = parse_caption(msg.raw_text, name)
        tags = meta["tags"] or self.settings.bili_tags
        status = await event.reply(f"Downloading {name} ({size / 1024 / 1024:.1f} MB) via MTProto…")
        tmpdir = tempfile.mkdtemp(prefix="toondown-")
        dest = Path(tmpdir) / name
        last_report = 0.0

        def progress(received: int, total: int) -> None:
            nonlocal last_report
            now = time.monotonic()
            if now - last_report < 8 and received < total:
                return
            last_report = now
            pct = (100.0 * received / total) if total else 0
            asyncio.get_event_loop().create_task(
                status.edit(
                    f"Downloading {name}: {pct:.0f}% "
                    f"({received / 1024 / 1024:.0f}/{max(total, 1) / 1024 / 1024:.0f} MB)"
                )
            )

        try:
            await self.client.download_media(
                msg, file=str(dest), progress_callback=progress
            )
            if not dest.exists() or dest.stat().st_size <= 0:
                await status.edit("Download produced an empty file.")
                return

            notes: list[str] = []

            if self.settings.adb_enabled:
                await status.edit(f"adb push {name} → emulator/device…")
                try:
                    pushed = await push_file(
                        str(dest),
                        adb_bin=self.settings.adb_bin,
                        serial=self.settings.adb_serial,
                        remote_dir=self.settings.adb_remote_dir,
                    )
                    notes.append(
                        f"ADB: {pushed.remote_path}\n"
                        "Open the international Bilibili app → Upload and pick that file."
                    )
                except AdbError as exc:
                    notes.append(f"ADB failed: {exc}")

            if self.settings.bili_ready:
                await status.edit(f"Uploading to bilibili.com as {meta['title']}…")
                async with BiliWebUploader(
                    self.settings.bili_sessdata,
                    self.settings.bili_jct,
                    self.settings.bili_dedeuserid,
                ) as bili:
                    result = await bili.upload_and_submit(
                        str(dest),
                        meta["title"],
                        tid=self.settings.bili_tid,
                        tags=tags,
                        desc=meta["desc"],
                        copyright=self.settings.bili_copyright,
                        source=meta["source"],
                    )
                link = (
                    f"https://www.bilibili.com/video/{result.bvid}"
                    if result.bvid
                    else "(waiting for bvid / review)"
                )
                notes.append(
                    f"mainland: bvid={result.bvid} aid={result.aid}\n{link}"
                )

            await status.edit("\n\n".join(notes) or "Done, nothing to report.")
        except BiliError as exc:
            log.warning("bili: %s", exc)
            await status.edit(f"Bilibili rejected the upload: {exc}")
        except Exception as exc:  # noqa: BLE001
            log.exception("job failed")
            await status.edit(f"Failed: {exc}")
        finally:
            try:
                if dest.exists():
                    dest.unlink()
                os.rmdir(tmpdir)
            except OSError:
                pass
