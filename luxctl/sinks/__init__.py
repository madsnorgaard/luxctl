"""Status sinks.

A "sink" is anything that reflects the current `ComputedState` outwards.
The daemon calls `apply()` on every sink whenever the resolved state
changes.

Today's sinks:

  * `LuxaforSink` — drives the physical light.
  * `LogSink` — appends every transition to ~/.local/state/luxctl/log.jsonl.
  * `SlackSink` — sets Slack status text + emoji + DND.

A sink that fails (network down, device unplugged, …) is logged but
does not stop other sinks from receiving the state.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from ..types import ComputedState


class Sink(ABC):
    name: str = "unknown"

    @abstractmethod
    def apply(self, current: ComputedState) -> None:
        """Reflect the resolved state. Idempotent — called repeatedly,
        but the daemon only calls it when the state has actually changed."""

    def close(self) -> None:
        """Release any held resources."""


from .luxafor import LuxaforSink  # noqa: E402
from .log import LogSink  # noqa: E402

__all__ = ["Sink", "LuxaforSink", "LogSink"]


def __getattr__(name):
    if name == "SlackSink":
        from .slack import SlackSink as _SS
        return _SS
    raise AttributeError(name)
