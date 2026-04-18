"""LockSource: screen-lock state via systemd-logind.

Polls `loginctl show-session $XDG_SESSION_ID -p LockedHint` once per call.
A daemon could subscribe to D-Bus signals for instant updates; polling is
chosen here to keep the implementation dependency-free.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from typing import Callable, Optional

from ..types import Declaration
from . import Source


def _read_locked_hint() -> Optional[bool]:
    if not shutil.which("loginctl"):
        return None
    session = os.environ.get("XDG_SESSION_ID", "auto")
    try:
        out = subprocess.check_output(
            ["loginctl", "show-session", session, "-p", "LockedHint"],
            stderr=subprocess.DEVNULL,
            timeout=2,
        ).decode().strip()
    except subprocess.SubprocessError:
        return None
    # Output: 'LockedHint=yes' or 'LockedHint=no'
    if "=" not in out:
        return None
    value = out.split("=", 1)[1].strip().lower()
    return value in ("yes", "true", "1")


class LockSource(Source):
    """Declares `locked_status` whenever the user's session is locked."""

    name = "lock"
    priority = 30

    def __init__(
        self,
        locked_status: str = "offline",
        reader: Optional[Callable[[], Optional[bool]]] = None,
    ) -> None:
        self.locked_status = locked_status
        self._read = reader or _read_locked_hint

    def current(self) -> Optional[Declaration]:
        locked = self._read()
        if not locked:
            return None
        return Declaration(
            status=self.locked_status,
            source=self.name,
            priority=self.priority,
            detail="screen locked",
        )
