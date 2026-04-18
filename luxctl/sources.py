"""Status sources.

A "source" is anything that can declare what the light *should* be showing.
Today only the user (`ManualSource`) sets the light, via the CLI or tray.

Future sources (not yet implemented) will plug in here:

  * `CalendarSource` — read an iCal feed, set "meeting" while a calendar
    event is active.
  * `SlackSource` / `TeamsSource` — webhook driven; flip to "busy" when
    presence flips to away.
  * `MuteButtonSource` — Luxafor's own mute-button hardware, mapped to a
    couple of preset toggles.

Sources have a priority (higher wins). A daemon (also future work) will
poll every registered source and apply the highest-priority non-None
declaration. Until that daemon exists, the priority field documents the
intended override order.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional

from . import state as state_module


@dataclass
class Declaration:
    """What a source thinks the light should currently be showing."""

    status: str
    source: str
    priority: int


class Source(ABC):
    """A pluggable status source. Implement `current()`."""

    name: str = "unknown"
    priority: int = 0

    @abstractmethod
    def current(self) -> Optional[Declaration]:
        """Return the source's current declaration, or None if idle."""


class ManualSource(Source):
    """The user, setting the light via CLI or tray. Lowest priority."""

    name = "manual"
    priority = 0

    def current(self) -> Optional[Declaration]:
        s = state_module.load()
        if s is None or s.source != self.name or s.status is None:
            return None
        return Declaration(status=s.status, source=self.name, priority=self.priority)


def resolve(sources: list[Source]) -> Optional[Declaration]:
    """Pick the highest-priority non-None declaration. Ties: first wins."""
    declarations = [d for s in sources if (d := s.current()) is not None]
    if not declarations:
        return None
    return max(declarations, key=lambda d: d.priority)
