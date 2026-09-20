"""Push a file to a local Android emulator or USB device.

This is not an upload into the Bilibili app. It only drops the video in
Download/ so you can tap Upload yourself on wired internet.

Koyeb free cannot run an emulator (no KVM, 512 MB RAM). Use this on a PC.
"""

from __future__ import annotations

import asyncio
import logging
import os
from dataclasses import dataclass

log = logging.getLogger("toondown.adb")


@dataclass
class AdbResult:
    remote_path: str
    log: str


class AdbError(RuntimeError):
    pass


async def push_file(
    local_path: str,
    *,
    adb_bin: str = "adb",
    serial: str = "",
    remote_dir: str = "/sdcard/Download/toondown",
) -> AdbResult:
    name = os.path.basename(local_path)
    remote_dir = remote_dir.rstrip("/")
    remote_path = f"{remote_dir}/{name}"

    prefix = [adb_bin]
    if serial:
        prefix.extend(["-s", serial])

    mkdir = prefix + ["shell", "mkdir", "-p", remote_dir]
    push = prefix + ["push", local_path, remote_path]

    await _run(mkdir, ignore_fail=True)
    code, out = await _run(push)
    if code != 0:
        raise AdbError(out or "adb push failed")
    return AdbResult(remote_path=remote_path, log=out)


async def _run(cmd: list[str], ignore_fail: bool = False) -> tuple[int, str]:
    log.info("adb: %s", " ".join(cmd))
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )
    raw, _ = await proc.communicate()
    text = (raw or b"").decode("utf-8", "replace").strip()
    code = proc.returncode or 0
    if code != 0 and not ignore_fail:
        log.warning("adb failed (%s): %s", code, text)
    return code, text
