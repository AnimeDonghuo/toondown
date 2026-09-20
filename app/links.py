from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import unquote, urlparse

URL_RE = re.compile(r"https?://[^\s<>\"']+", re.I)
TME_RE = re.compile(
    r"^https?://(?:t\.me|telegram\.me|telegram\.dog)/"
    r"(?:c/(\d+)|([A-Za-z0-9_]+))/(\d+)",
    re.I,
)


@dataclass(frozen=True)
class TgMessageRef:
    chat: int | str
    msg_id: int


def extract_urls(text: str | None) -> list[str]:
    if not text:
        return []
    return [u.rstrip(").,]") for u in URL_RE.findall(text)]


def strip_urls(text: str | None) -> str:
    if not text:
        return ""
    cleaned = URL_RE.sub("", text)
    lines = [ln.rstrip() for ln in cleaned.splitlines()]
    while lines and not lines[0].strip():
        lines.pop(0)
    while lines and not lines[-1].strip():
        lines.pop()
    return "\n".join(lines).strip()


def parse_tme(url: str) -> TgMessageRef | None:
    m = TME_RE.match(url.strip())
    if not m:
        return None
    private_id, username, msg_id = m.group(1), m.group(2), int(m.group(3))
    if private_id:
        return TgMessageRef(chat=int(f"-100{private_id}"), msg_id=msg_id)
    if username and username.lower() not in {"s", "joinchat", "addstickers", "socks", "proxy"}:
        return TgMessageRef(chat=username, msg_id=msg_id)
    return None


def filename_from_url(url: str, fallback: str = "video.mp4") -> str:
    path = unquote(urlparse(url).path)
    name = path.rsplit("/", 1)[-1]
    name = name.replace("/", "_").strip()
    if not name or "." not in name:
        return fallback
    return name[:180]


def is_safe_http_url(url: str) -> bool:
    p = urlparse(url)
    if p.scheme not in {"http", "https"}:
        return False
    host = (p.hostname or "").lower().rstrip(".")
    if not host or host in {"localhost", "127.0.0.1", "::1", "0.0.0.0"}:
        return False
    if host.endswith(".local") or host.endswith(".internal"):
        return False
    if host.startswith("169.254.") or host.startswith("10.") or host.startswith("192.168."):
        return False
    if re.match(r"^172\.(1[6-9]|2\d|3[0-1])\.", host):
        return False
    return True
