"""Status sources.

A "source" is anything that can declare what the light *should* be
showing. The daemon polls every registered source and resolves the
highest-priority non-None declaration.

Today's sources:

  * `ManualSource` — the user via CLI or tray.
  * `IdleSource` — input-idleness detection (sets "offline"/"brb").
  * `LockSource` — screen-lock state (sets "offline").
  * `CalendarSource` — iCal feed; sets "meeting" while an event is on.
  * `SlackSource` — reads Slack presence (active/away).

Each source declares a default `priority`. Higher beats lower. The
intended order from low to high is:

    manual (0)  <  idle (10)  <  calendar (20)  <  lock (30)  <  slack (40)

i.e. the screen lock and Slack-set DND override calendar; calendar
overrides idle; idle overrides manual.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from ..types import Declaration


class Source(ABC):
    """A pluggable status source. Implement `current()`."""

    name: str = "unknown"
    priority: int = 0

    @abstractmethod
    def current(self) -> Optional[Declaration]:
        """Return the source's current declaration, or None if idle."""

    def close(self) -> None:
        """Release any held resources. Default: no-op."""


def resolve(sources: list[Source]) -> Optional[Declaration]:
    """Pick the highest-priority non-None declaration. Ties: first wins."""
    declarations = [d for s in sources if (d := s.current()) is not None]
    if not declarations:
        return None
    return max(declarations, key=lambda d: d.priority)


from .manual import ManualSource  # noqa: E402
from .idle import IdleSource  # noqa: E402
from .lock import LockSource  # noqa: E402

__all__ = [
    "Source",
    "Declaration",
    "ManualSource",
    "IdleSource",
    "LockSource",
    "resolve",
]

# CalendarSource and SlackSource use optional deps — lazy import.
def __getattr__(name):
    if name == "CalendarSource":
        from .calendar import CalendarSource as _CS
        return _CS
    if name == "SlackSource":
        from .slack import SlackSource as _SS
        return _SS
    raise AttributeError(name)
