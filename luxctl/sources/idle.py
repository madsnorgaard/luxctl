"""IdleSource: input idleness via the GNOME Mutter idle monitor (Wayland-friendly).

Falls back to xprintidle on X11. If neither works, current() returns None
(the source becomes a no-op rather than crashing the daemon).
"""

from __future__ import annotations

import re
import shutil
import subprocess
from typing import Callable, Optional

from ..types import Declaration
from . import Source


def _read_idle_ms_via_mutter() -> Optional[int]:
    cmd = [
        "gdbus", "call", "--session",
        "--dest=org.gnome.Mutter.IdleMonitor",
        "--object-path=/org/gnome/Mutter/IdleMonitor/Core",
        "--method=org.gnome.Mutter.IdleMonitor.GetIdletime",
    ]
    try:
        out = subprocess.check_output(cmd, stderr=subprocess.DEVNULL, timeout=2).decode()
    except (FileNotFoundError, subprocess.SubprocessError):
        return None
    # Output looks like: '(uint64 12345,)'
    m = re.search(r"(\d+)", out)
    return int(m.group(1)) if m else None


def _read_idle_ms_via_xprintidle() -> Optional[int]:
    if not shutil.which("xprintidle"):
        return None
    try:
        out = subprocess.check_output(["xprintidle"], timeout=2).decode().strip()
        return int(out)
    except (subprocess.SubprocessError, ValueError):
        return None


def _read_idle_ms() -> Optional[int]:
    return _read_idle_ms_via_mutter() or _read_idle_ms_via_xprintidle()


class IdleSource(Source):
    """Declares 'brb' after `away_minutes` of input idleness, 'offline' after `offline_minutes`."""

    name = "idle"
    priority = 10

    def __init__(
        self,
        away_minutes: int = 5,
        offline_minutes: int = 30,
        away_status: str = "brb",
        offline_status: str = "offline",
        idle_reader: Optional[Callable[[], Optional[int]]] = None,
    ) -> None:
        self.away_ms = away_minutes * 60_000
        self.offline_ms = offline_minutes * 60_000
        self.away_status = away_status
        self.offline_status = offline_status
        self._read = idle_reader or _read_idle_ms

    def current(self) -> Optional[Declaration]:
        idle_ms = self._read()
        if idle_ms is None:
            return None
        if idle_ms >= self.offline_ms:
            return Declaration(
                status=self.offline_status,
                source=self.name,
                priority=self.priority,
                detail=f"idle {idle_ms // 60_000}m",
            )
        if idle_ms >= self.away_ms:
            return Declaration(
                status=self.away_status,
                source=self.name,
                priority=self.priority,
                detail=f"idle {idle_ms // 60_000}m",
            )
        return None
