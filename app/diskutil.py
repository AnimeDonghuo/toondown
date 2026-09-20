from __future__ import annotations

import shutil
from pathlib import Path


def free_bytes(path: str | Path = "/tmp") -> int:
    return shutil.disk_usage(path).free


def max_file_bytes(cap_mb: int, reserve_mb: int = 300, path: str | Path = "/tmp") -> int:
    cap = max(1, cap_mb) * 1024 * 1024
    usable = max(0, free_bytes(path) - reserve_mb * 1024 * 1024)
    return min(cap, usable)
