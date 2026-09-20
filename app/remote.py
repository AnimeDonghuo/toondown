"""Fetch a remote HTTP file in chunks (never load the whole video into RAM)."""

from __future__ import annotations

import logging
from collections.abc import Callable
from pathlib import Path

import httpx

from app.links import filename_from_url, is_safe_http_url

log = logging.getLogger("toondown.remote")

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
)

Progress = Callable[[int, int], None]


class RemoteError(RuntimeError):
    pass


async def download_http(
    url: str,
    dest_dir: str | Path,
    *,
    max_bytes: int,
    progress: Progress | None = None,
) -> Path:
    if not is_safe_http_url(url):
        raise RemoteError("URL not allowed (need public http/https)")

    timeout = httpx.Timeout(connect=30.0, read=300.0, write=60.0, pool=30.0)
    name = filename_from_url(url)
    dest = Path(dest_dir) / name

    async with httpx.AsyncClient(
        timeout=timeout,
        follow_redirects=True,
        headers={"User-Agent": UA},
    ) as client:
        async with client.stream("GET", url) as resp:
            if resp.status_code >= 400:
                raise RemoteError(f"HTTP {resp.status_code} for {url}")
            ctype = (resp.headers.get("content-type") or "").split(";")[0].strip().lower()
            if ctype.startswith("text/html") or ctype in {"application/json", "text/plain"}:
                raise RemoteError(
                    f"URL is {ctype or 'not a file'}. Send a direct .mp4/.mkv link, "
                    "a t.me message link, or the video itself."
                )
            total = int(resp.headers.get("content-length") or 0)
            if total and total > max_bytes:
                raise RemoteError(
                    f"Remote file is {total / 1024 / 1024:.1f} MB, cap is "
                    f"{max_bytes / 1024 / 1024:.0f} MB"
                )
            got = 0
            with dest.open("wb") as fh:
                async for chunk in resp.aiter_bytes(1024 * 1024):
                    got += len(chunk)
                    if got > max_bytes:
                        fh.close()
                        dest.unlink(missing_ok=True)
                        raise RemoteError(
                            f"Download exceeded cap {max_bytes / 1024 / 1024:.0f} MB"
                        )
                    fh.write(chunk)
                    if progress:
                        progress(got, total or got)
    if dest.stat().st_size <= 0:
        dest.unlink(missing_ok=True)
        raise RemoteError("empty download")
    log.info("http downloaded %s (%s bytes)", dest, dest.stat().st_size)
    return dest
