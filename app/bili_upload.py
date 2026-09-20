"""Mainland bilibili.com web (UPOS) uploader.

This is the same cookie flow the member.bilibili.com studio uses.
It does NOT talk to the 2026 international Android app — that product has
no public upload API.
"""

from __future__ import annotations

import json
import logging
import math
import os
import time
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlencode

import httpx

log = logging.getLogger("toondown.bili")

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
)
PREUPLOAD = "https://member.bilibili.com/preupload"
SUBMIT = "https://member.bilibili.com/x/vu/web/add/v3"
NAV = "https://api.bilibili.com/x/web-interface/nav"


class BiliError(RuntimeError):
    pass


@dataclass
class UploadResult:
    aid: int | None
    bvid: str | None
    raw: dict[str, Any]


def _cookie_header(sessdata: str, jct: str, dede: str) -> str:
    parts = [f"SESSDATA={sessdata}", f"bili_jct={jct}"]
    if dede:
        parts.append(f"DedeUserID={dede}")
    return "; ".join(parts)


class BiliWebUploader:
    def __init__(
        self,
        sessdata: str,
        jct: str,
        dedeuserid: str = "",
        timeout: float = 300.0,
    ) -> None:
        if not sessdata or not jct:
            raise BiliError("BILI_SESSDATA and BILI_JCT are required")
        self.jct = jct
        self.client = httpx.AsyncClient(
            timeout=httpx.Timeout(timeout, connect=30.0),
            headers={
                "User-Agent": UA,
                "Cookie": _cookie_header(sessdata, jct, dedeuserid),
                "Origin": "https://member.bilibili.com",
                "Referer": "https://member.bilibili.com/platform/upload/video/frame",
            },
            follow_redirects=True,
        )

    async def aclose(self) -> None:
        await self.client.aclose()

    async def whoami(self) -> dict[str, Any]:
        r = await self.client.get(NAV)
        r.raise_for_status()
        data = r.json()
        if data.get("code") != 0:
            raise BiliError(f"login check failed: {data.get('message')}")
        inner = data.get("data") or {}
        if not inner.get("isLogin"):
            raise BiliError("SESSDATA expired or invalid (not logged in)")
        return inner

    async def upload_and_submit(
        self,
        path: str,
        title: str,
        *,
        tid: int,
        tags: str,
        desc: str = "",
        copyright: int = 1,
        source: str = "",
    ) -> UploadResult:
        filename = os.path.basename(path)
        size = os.path.getsize(path)
        if size <= 0:
            raise BiliError("empty file")

        me = await self.whoami()
        log.info("logged in as mid=%s name=%s", me.get("mid"), me.get("uname"))

        part = await self._upload_file(path, filename, size)
        payload = {
            "copyright": 2 if source else copyright,
            "videos": [
                {
                    "filename": part["filename"],
                    "title": title[:80],
                    "desc": "",
                    "cid": part["cid"],
                }
            ],
            "source": source,
            "tid": tid,
            "cover": "",
            "title": title[:80],
            "tag": tags[:200],
            "desc_format_id": 0,
            "desc": desc[:2000],
            "dynamic": "",
            "subtitle": {"open": 0, "lan": ""},
            "no_reprint": 1 if not source else 0,
            "web_os": 2,
            "csrf": self.jct,
        }
        qs = urlencode({"ts": int(time.time() * 1000), "csrf": self.jct})
        r = await self.client.post(
            f"{SUBMIT}?{qs}",
            json=payload,
            headers={"Content-Type": "application/json;charset=UTF-8"},
        )
        r.raise_for_status()
        body = r.json()
        if body.get("code") != 0:
            raise BiliError(
                f"submit failed code={body.get('code')} msg={body.get('message')}"
            )
        data = body.get("data") or {}
        return UploadResult(aid=data.get("aid"), bvid=data.get("bvid"), raw=body)

    async def _upload_file(self, path: str, name: str, size: int) -> dict[str, Any]:
        params = {
            "name": name,
            "size": str(size),
            "r": "upos",
            "profile": "ugcfx/bup",
            "ssl": "0",
            "version": "2.14.0",
            "build": "2140000",
        }
        r = await self.client.get(PREUPLOAD, params=params)
        r.raise_for_status()
        meta = r.json()
        if meta.get("OK") != 1 and "upos_uri" not in meta:
            raise BiliError(f"preupload failed: {meta}")

        upos_uri = str(meta["upos_uri"]).replace("upos://", "")
        auth = meta["auth"]
        biz_id = meta["biz_id"]
        chunk_size = int(meta.get("chunk_size") or 4 * 1024 * 1024)
        endpoint = meta.get("endpoint") or (meta.get("endpoints") or [None])[0]
        if not endpoint:
            raise BiliError("preupload returned no endpoint")
        if not endpoint.startswith("http"):
            endpoint = "https:" + endpoint

        base = f"{endpoint}/{upos_uri}"
        auth_headers = {"X-Upos-Auth": auth}

        init = await self.client.post(
            f"{base}?uploads&output=json", headers=auth_headers
        )
        init.raise_for_status()
        init_body = init.json()
        upload_id = init_body.get("upload_id")
        if not upload_id:
            raise BiliError(f"init multipart failed: {init_body}")

        chunks = max(1, math.ceil(size / chunk_size))
        parts: list[dict[str, Any]] = []
        log.info("uploading %s (%s bytes, %s chunks)", name, size, chunks)

        with open(path, "rb") as fh:
            for index in range(chunks):
                data = fh.read(chunk_size)
                start = index * chunk_size
                end = start + len(data) - 1
                q = {
                    "partNumber": str(index + 1),
                    "uploadId": upload_id,
                    "chunk": str(index),
                    "chunks": str(chunks),
                    "size": str(len(data)),
                    "start": str(start),
                    "end": str(end),
                    "total": str(size),
                }
                put = await self.client.put(
                    f"{base}?{urlencode(q)}",
                    content=data,
                    headers=auth_headers,
                )
                put.raise_for_status()
                etag = put.headers.get("Etag") or put.headers.get("ETag") or "etag"
                parts.append({"partNumber": index + 1, "eTag": etag.strip('"')})
                log.info("chunk %s/%s ok", index + 1, chunks)

        complete_q = {
            "output": "json",
            "name": name,
            "profile": "ugcfx/bup",
            "uploadId": upload_id,
            "biz_id": str(biz_id),
        }
        complete = await self.client.post(
            f"{base}?{urlencode(complete_q)}",
            content=json.dumps({"parts": parts}),
            headers={**auth_headers, "Content-Type": "application/json"},
        )
        complete.raise_for_status()
        cbody = complete.json()
        if cbody.get("OK") != 1 and cbody.get("code") not in (0, None):
            raise BiliError(f"complete failed: {cbody}")

        # filename for submit is the upos object name without extension
        object_name = upos_uri.rsplit("/", 1)[-1]
        stem = object_name.rsplit(".", 1)[0]
        return {"filename": stem, "cid": biz_id, "title": name}

    async def __aenter__(self) -> "BiliWebUploader":
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.aclose()


def parse_caption(caption: str | None, fallback_name: str) -> dict[str, str]:
    """Caption layout:

    line 1: title
    line 2: comma-separated tags (optional)
    rest: description; a line starting with source: becomes reprint source
    """
    text = (caption or "").strip()
    title = fallback_name.rsplit(".", 1)[0][:80]
    tags = ""
    desc_lines: list[str] = []
    source = ""
    if not text:
        return {"title": title, "tags": tags, "desc": "", "source": ""}

    lines = text.splitlines()
    title = lines[0].strip()[:80] or title
    rest = lines[1:]
    if rest and ("," in rest[0] or (rest[0] and " " not in rest[0] and len(rest[0]) < 80)):
        # treat second line as tags when it looks like a tag list
        maybe = rest[0].strip()
        if maybe.lower().startswith("tags:"):
            tags = maybe.split(":", 1)[1].strip()
            rest = rest[1:]
        elif "," in maybe:
            tags = maybe
            rest = rest[1:]
    for line in rest:
        stripped = line.strip()
        low = stripped.lower()
        if low.startswith("source:"):
            source = stripped.split(":", 1)[1].strip()
        else:
            desc_lines.append(line)
    return {
        "title": title,
        "tags": tags,
        "desc": "\n".join(desc_lines).strip(),
        "source": source,
    }
