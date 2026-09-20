from __future__ import annotations

import shutil
from pathlib import Path


def ensure_dir(path: str | Path) -> Path:
    p = Path(path)
    p.mkdir(parents=True, exist_ok=True)
    return p


def free_bytes(path: str | Path) -> int:
    ensure_dir(path)
    return shutil.disk_usage(path).free


def total_bytes(path: str | Path) -> int:
    ensure_dir(path)
    return shutil.disk_usage(path).total


def max_file_bytes(cap_mb: int, reserve_mb: int = 400, path: str | Path = "/tmp") -> int:
    cap = max(1, cap_mb) * 1024 * 1024
    usable = max(0, free_bytes(path) - reserve_mb * 1024 * 1024)
    return min(cap, usable)


def human_bytes(n: int) -> str:
    if n >= 1024**3:
        return f" {n / 1024**3:.1f} GB".strip()
    return f"{n / 1024**2:.0f} MB"
