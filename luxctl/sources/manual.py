"""Manual source: reads whatever the user last set via CLI or tray."""

from __future__ import annotations

from typing import Optional

from .. import state as state_module
from ..types import Declaration
from . import Source


MANUAL_SOURCES = {"manual", "tray", "cli"}


class ManualSource(Source):
    name = "manual"
    priority = 0

    def current(self) -> Optional[Declaration]:
        s = state_module.load()
        if s is None or s.source not in MANUAL_SOURCES or s.status is None:
            return None
        return Declaration(
            status=s.status,
            source=self.name,
            priority=self.priority,
            detail=s.active_task,
        )
