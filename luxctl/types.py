"""Shared dataclasses passed between sources, sinks, and the daemon."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class Declaration:
    """What a source thinks the light should currently be showing.

    Higher `priority` wins when multiple sources declare at once.
    `detail` is optional context that sinks may use (e.g. the calendar
    event title, becoming the Slack status text).
    """

    status: str
    source: str
    priority: int
    detail: Optional[str] = None


@dataclass(frozen=True)
class ComputedState:
    """The daemon's resolved view of the world.

    Sinks consume this and reflect it. Equality is used by the daemon
    to detect "no change → skip apply".
    """

    status: str
    source: str
    active_task: Optional[str] = None
    detail: Optional[str] = None

    def display_text(self) -> str:
        """Best human-readable string for this state. Used by SlackSink as
        status_text and by the tray as the header line."""
        if self.active_task:
            return self.active_task
        if self.detail:
            return self.detail
        return self.status.replace("-", " ").capitalize()
