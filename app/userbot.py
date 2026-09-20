from __future__ import annotations

import asyncio
import logging
import time
from pathlib import Path

from telethon import TelegramClient, events
from telethon.tl.custom import Message

from app.adb_push import AdbError, push_file
from app.bili_upload import BiliError, BiliWebUploader, parse_caption
from app.config import Settings
from app.diskutil import ensure_dir, free_bytes, human_bytes, max_file_bytes, total_bytes
from app.links import TgMessageRef, extract_urls, parse_tme, strip_urls
from app.remote import RemoteError, download_http

log = logging.getLogger("toondown.userbot")

HELP = (
    "Send or forward a video here (MTProto, up to 2 GB / 4 GB Premium).\n"
    "Or send a remote link:\n"
    "  • t.me/channel/123  (this account must be able to see it)\n"
    "  • https://example.com/file.mp4  (direct file URL)\n"
    "  • /dl <url>\n\n"
    "Caption / text around the link:\n"
    "  Title\n"
    "  tag1,tag2\n"
    "  description\n"
    "  source: https://...   (reprint only)\n\n"
    "/help  /whoami  /status\n\n"
    "Disk is whatever this container actually has (Koyeb official free "
    "instance is 2 GB SSD; if yours is larger, /status will show it).\n"
    "Mainland Bilibili: SESSDATA cookies. Intl app: no API — ADB on a PC."
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


class Progress:
    def __init__(self, status: Message, label: str) -> None:
        self.status = status
        self.label = label
        self.last = 0.0
        self.loop = asyncio.get_running_loop()

    def __call__(self, received: int, total: int) -> None:
        now = time.monotonic()
        if now - self.last < 10 and total and received < total:
            return
        self.last = now
        pct = (100.0 * received / total) if total else 0
        text = (
            f"{self.label}: {pct:.0f}% "
            f"({human_bytes(received)}/{human_bytes(total or received)})"
        )

        async def _edit() -> None:
            try:
                await self.status.edit(text)
            except Exception:
                return

        self.loop.call_soon_threadsafe(lambda: self.loop.create_task(_edit()))


class Worker:
    def __init__(self, client: TelegramClient, settings: Settings) -> None:
        self.client = client
        self.settings = settings
        self.lock = asyncio.Lock()
        self.allowed: set[int] = set(settings.allowed_user_ids)
        self.self_id = 0
        self.data_dir = ensure_dir(settings.data_dir)

    async def start(self) -> None:
        me = await self.client.get_me()
        self.self_id = int(me.id)
        self.allowed.add(self.self_id)
        log.info("logged in as id=%s username=%s data=%s", me.id, me.username, self.data_dir)

        @self.client.on(events.NewMessage(incoming=True, outgoing=True))
        async def _on_msg(event: events.NewMessage.Event) -> None:
            await self.on_message(event)

    def _ok_user(self, msg: Message) -> bool:
        sender = msg.sender_id
        return sender is not None and int(sender) in self.allowed

    def _cap(self) -> int:
        return max_file_bytes(self.settings.max_file_mb, path=self.data_dir)

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

        urls = extract_urls(text)
        if text.startswith("/dl"):
            rest = text[3:].strip()
            urls = extract_urls(rest) or ([rest] if rest.startswith("http") else urls)
            if not urls:
                await event.reply("Usage: /dl https://t.me/c/…/123  or  /dl https://host/file.mp4")
                return
            await self.handle_remote(event, urls, strip_urls(rest))
            return

        if msg.video or msg.document or msg.gif:
            await self.handle_media(event)
            return

        if urls:
            await self.handle_remote(event, urls, strip_urls(text))
            return

        if text and not text.startswith("/"):
            await event.reply("Send a video, forward one, or paste a t.me / direct .mp4 link. /help")

    async def status_text(self) -> str:
        s = self.settings
        total = total_bytes(self.data_dir)
        free = free_bytes(self.data_dir)
        cap = self._cap()
        lines = [
            "transport: MTProto (Telethon user account)",
            f"data dir: {self.data_dir}",
            f"disk total: {human_bytes(total)}",
            f"disk free: {human_bytes(free)}",
            f"usable this job: {human_bytes(cap)} (MAX_FILE_MB={s.max_file_mb})",
            f"mainland cookies: {'yes' if s.bili_ready else 'NO'}",
            f"adb push: {'on' if s.adb_enabled else 'off'}",
            "intl app API: none",
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

    def _need_dest(self) -> str | None:
        if self.settings.bili_ready or self.settings.adb_enabled:
            return None
        return (
            "No destination configured.\n"
            "- mainland: set BILI_SESSDATA + BILI_JCT\n"
            "- intl app on a PC emulator: ADB_ENABLED=1"
        )

    async def handle_media(self, event: events.NewMessage.Event) -> None:
        if self.lock.locked():
            await event.reply("Busy with another file. Retry in a minute.")
            return
        msg: Message = event.message
        name = _name_of(msg)
        size = _size_of(msg)
        cap = self._cap()
        if size and size > cap:
            await event.reply(
                f"{name} is {human_bytes(size)}. This host can take "
                f"{human_bytes(cap)} right now (free disk minus reserve)."
            )
            return
        err = self._need_dest()
        if err:
            await event.reply(err)
            return
        async with self.lock:
            await self._download_tg_message(event, msg, name, size, msg.raw_text)

    async def handle_remote(
        self, event: events.NewMessage.Event, urls: list[str], caption: str
    ) -> None:
        if self.lock.locked():
            await event.reply("Busy with another file. Retry in a minute.")
            return
        err = self._need_dest()
        if err:
            await event.reply(err)
            return
        url = urls[0]
        async with self.lock:
            tme = parse_tme(url)
            if tme:
                await self._download_tme(event, tme, caption)
                return
            await self._download_http(event, url, caption)

    async def _download_tme(
        self, event: events.NewMessage.Event, ref: TgMessageRef, caption: str
    ) -> None:
        try:
            remote = await self.client.get_messages(ref.chat, ids=ref.msg_id)
        except Exception as exc:  # noqa: BLE001
            await event.reply(f"Cannot open that Telegram message: {exc}")
            return
        if not remote or not (remote.video or remote.document or remote.gif):
            await event.reply("That t.me link has no video/file this account can see.")
            return
        name = _name_of(remote)
        size = _size_of(remote)
        cap = self._cap()
        if size and size > cap:
            await event.reply(
                f"{name} is {human_bytes(size)}, cap is {human_bytes(cap)}."
            )
            return
        text = caption or remote.raw_text
        await self._download_tg_message(event, remote, name, size, text)

    async def _download_http(
        self, event: events.NewMessage.Event, url: str, caption: str
    ) -> None:
        cap = self._cap()
        status = await event.reply(f"Fetching remote URL (cap {human_bytes(cap)})…")
        job_dir = ensure_dir(self.data_dir / f"job-{int(time.time())}")
        dest: Path | None = None
        try:
            dest = await download_http(
                url, job_dir, max_bytes=cap, progress=Progress(status, "HTTP")
            )
            await self._publish(status, dest, caption or dest.name)
        except RemoteError as exc:
            await status.edit(str(exc))
        except Exception as exc:  # noqa: BLE001
            log.exception("http job")
            await status.edit(f"Failed: {exc}")
        finally:
            self._cleanup(job_dir, dest)

    async def _download_tg_message(
        self,
        event: events.NewMessage.Event,
        media_msg: Message,
        name: str,
        size: int,
        caption: str | None,
    ) -> None:
        status = await event.reply(
            f"Downloading {name} ({human_bytes(size)}) from Telegram via MTProto…"
        )
        job_dir = ensure_dir(self.data_dir / f"job-{int(time.time())}")
        dest = job_dir / name
        try:
            await self.client.download_media(
                media_msg,
                file=str(dest),
                progress_callback=Progress(status, f"TG {name}"),
            )
            if not dest.exists() or dest.stat().st_size <= 0:
                await status.edit("Download produced an empty file.")
                return
            await self._publish(status, dest, caption or name)
        except Exception as exc:  # noqa: BLE001
            log.exception("tg job")
            await status.edit(f"Failed: {exc}")
        finally:
            self._cleanup(job_dir, dest)

    async def _publish(self, status: Message, dest: Path, caption: str) -> None:
        meta = parse_caption(caption, dest.name)
        tags = meta["tags"] or self.settings.bili_tags
        notes: list[str] = []

        if self.settings.adb_enabled:
            await status.edit(f"adb push {dest.name}…")
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
            notes.append(f"mainland: bvid={result.bvid} aid={result.aid}\n{link}")

        await status.edit("\n\n".join(notes) or "Done.")

    def _cleanup(self, job_dir: Path, dest: Path | None) -> None:
        try:
            if dest and dest.exists():
                dest.unlink()
            job_dir.rmdir()
        except OSError:
            pass
