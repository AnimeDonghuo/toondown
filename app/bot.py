from __future__ import annotations

import logging
import os
import tempfile
from pathlib import Path
from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware, Bot, Dispatcher, F, Router
from aiogram.filters import Command, CommandStart
from aiogram.types import Message, TelegramObject

from app.bili_upload import BiliError, BiliWebUploader, parse_caption
from app.config import Settings

log = logging.getLogger("toondown.bot")
router = Router()

INTL_BLURB = (
    "The 2026 international Bilibili app (pink icon + globe) has *no public "
    "upload API*. Uploads are Android-app only; the English web studio is "
    "still listed as coming soon.\n\n"
    "This bot can submit to *mainland* member.bilibili.com if you set "
    "SESSDATA cookies. That is a different product and usually needs a "
    "real-name verified Chinese account.\n\n"
    "Faster than phone for the intl app today: copy the file to a PC, run "
    "an Android emulator on wired internet, and upload from there. Do not "
    "upload content you do not have rights to."
)


def _allowed(settings: Settings, user_id: int | None) -> bool:
    if user_id is None:
        return False
    if not settings.allowed_user_ids:
        return False
    return user_id in settings.allowed_user_ids


@router.message(CommandStart())
async def cmd_start(message: Message, settings: Settings) -> None:
    if not _allowed(settings, message.from_user.id if message.from_user else None):
        await message.answer("This bot is private. Your user id is not allowlisted.")
        return
    await message.answer(
        "Send a video (or a file) and I will try to publish it on "
        "*bilibili.com* (mainland studio).\n\n"
        "Caption format:\n"
        "`Title of the video`\n"
        "`tag1,tag2,tag3`\n"
        "`description…`\n"
        "`source: https://…`  ← only if this is a reprint\n\n"
        f"{INTL_BLURB}\n\n"
        "Telegram Bot API will not download files larger than ~20 MB. "
        "Koyeb free is 512 MB RAM / 2 GB disk and sleeps after idle — it is "
        "the wrong host for long HD videos.",
        parse_mode="Markdown",
    )


@router.message(Command("help"))
async def cmd_help(message: Message, settings: Settings) -> None:
    await cmd_start(message, settings)


@router.message(Command("whoami"))
async def cmd_whoami(message: Message) -> None:
    uid = message.from_user.id if message.from_user else 0
    await message.answer(f"Your Telegram user id: `{uid}`", parse_mode="Markdown")


@router.message(Command("status"))
async def cmd_status(message: Message, settings: Settings) -> None:
    if not _allowed(settings, message.from_user.id if message.from_user else None):
        await message.answer("Not allowlisted.")
        return
    lines = [
        f"mainland cookies set: {'yes' if settings.bili_ready else 'NO'}",
        f"tid: {settings.bili_tid}",
        f"default tags: {settings.bili_tags}",
        f"max file: {settings.max_file_mb} MB",
        "international app API: none",
    ]
    if settings.bili_ready:
        try:
            async with BiliWebUploader(
                settings.bili_sessdata,
                settings.bili_jct,
                settings.bili_dedeuserid,
            ) as bili:
                me = await bili.whoami()
            lines.append(f"bilibili login: {me.get('uname')} (mid {me.get('mid')})")
        except Exception as exc:  # noqa: BLE001
            lines.append(f"bilibili login: FAILED ({exc})")
    await message.answer("\n".join(lines))


def _pick_file(message: Message) -> tuple[str, int, str] | None:
    if message.video:
        v = message.video
        return v.file_id, v.file_size or 0, v.file_name or "video.mp4"
    if message.document:
        d = message.document
        return d.file_id, d.file_size or 0, d.file_name or "file.bin"
    if message.animation:
        a = message.animation
        return a.file_id, a.file_size or 0, a.file_name or "anim.mp4"
    return None


@router.message(F.video | F.document | F.animation)
async def on_media(message: Message, bot: Bot, settings: Settings) -> None:
    if not _allowed(settings, message.from_user.id if message.from_user else None):
        await message.answer("Not allowlisted. Send /whoami and add that id.")
        return

    picked = _pick_file(message)
    if not picked:
        await message.answer("No file on that message.")
        return
    file_id, size, name = picked
    cap = max(1, settings.max_file_mb) * 1024 * 1024
    if size and size > cap:
        await message.answer(
            f"`{name}` is {size / 1024 / 1024:.1f} MB. "
            f"Telegram bots cannot download more than ~20 MB (configured max "
            f"{settings.max_file_mb} MB). Put the file on a PC and use the "
            "mainland web studio, or an Android emulator for the intl app.",
            parse_mode="Markdown",
        )
        return

    if not settings.bili_ready:
        await message.answer(
            "Got the file, but mainland Bilibili cookies are not configured, "
            "and the international app has no upload API.\n\n" + INTL_BLURB
        )
        return

    meta = parse_caption(message.caption, name)
    tags = meta["tags"] or settings.bili_tags
    status = await message.answer(f"Downloading `{name}`…", parse_mode="Markdown")

    tmpdir = tempfile.mkdtemp(prefix="toondown-")
    dest = Path(tmpdir) / name.replace("/", "_")
    try:
        tg_file = await bot.get_file(file_id)
        await bot.download(tg_file, destination=dest)
        await status.edit_text(
            f"Uploading to bilibili.com as *{meta['title']}*…",
            parse_mode="Markdown",
        )
        async with BiliWebUploader(
            settings.bili_sessdata,
            settings.bili_jct,
            settings.bili_dedeuserid,
        ) as bili:
            result = await bili.upload_and_submit(
                str(dest),
                meta["title"],
                tid=settings.bili_tid,
                tags=tags,
                desc=meta["desc"],
                copyright=settings.bili_copyright,
                source=meta["source"],
            )
        link = (
            f"https://www.bilibili.com/video/{result.bvid}"
            if result.bvid
            else "(no bvid yet — wait for review)"
        )
        await status.edit_text(
            f"Submitted to mainland Bilibili.\n"
            f"bvid: `{result.bvid}`\naid: `{result.aid}`\n{link}\n\n"
            "It still has to pass Bilibili review.",
            parse_mode="Markdown",
        )
    except BiliError as exc:
        log.warning("bili error: %s", exc)
        await status.edit_text(f"Bilibili rejected the upload: {exc}")
    except Exception as exc:  # noqa: BLE001
        log.exception("upload failed")
        await status.edit_text(f"Upload failed: {exc}")
    finally:
        try:
            if dest.exists():
                dest.unlink()
            os.rmdir(tmpdir)
        except OSError:
            pass


@router.message()
async def fallback(message: Message, settings: Settings) -> None:
    if not _allowed(settings, message.from_user.id if message.from_user else None):
        return
    await message.answer("Send a video, or /help.")


class SettingsMiddleware(BaseMiddleware):
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        data["settings"] = self.settings
        return await handler(event, data)


def build_dispatcher(settings: Settings) -> Dispatcher:
    dp = Dispatcher()
    dp["settings"] = settings
    dp.message.middleware(SettingsMiddleware(settings))
    dp.include_router(router)
    return dp
