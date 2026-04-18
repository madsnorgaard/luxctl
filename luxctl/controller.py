"""High-level orchestration: open the device once, apply state to all sinks.

Used by both the one-shot CLI commands and the long-running daemon. The
daemon constructs one Controller and reuses it; CLI commands construct
a controller per invocation.
"""

from __future__ import annotations

from typing import Optional

from . import state as state_module
from .device import LuxaforError, LuxaforFlag
from .sinks import LogSink, LuxaforSink, Sink
from .state import State, now_iso
from .statuses import STATUSES
from .types import ComputedState

# Sentinel for "don't change the active task" (vs. None which means "clear it").
_KEEP_TASK = object()


class Controller:
    """Owns a LuxaforFlag handle and a list of sinks."""

    def __init__(
        self,
        sinks: Optional[list[Sink]] = None,
        light: Optional[LuxaforFlag] = None,
    ) -> None:
        self._light = light
        if sinks is None:
            self._light = self._light or LuxaforFlag()
            sinks = [LuxaforSink(self._light), LogSink()]
        self.sinks = sinks

    def apply(self, current: ComputedState) -> list[tuple[str, Optional[Exception]]]:
        """Push state to every sink. Returns (sink_name, error_or_None) per sink."""
        results: list[tuple[str, Optional[Exception]]] = []
        for sink in self.sinks:
            try:
                sink.apply(current)
                results.append((sink.name, None))
            except Exception as exc:
                results.append((sink.name, exc))
        return results

    def apply_status(
        self,
        name: str,
        source: str = "manual",
        active_task=_KEEP_TASK,
    ) -> list[tuple[str, Optional[Exception]]]:
        """One-shot helper: validate status, build ComputedState, apply, persist.

        `active_task` defaults to a sentinel meaning "leave the existing task
        alone". Pass `None` to explicitly clear it, or a string to set it.
        """
        if name not in STATUSES:
            raise ValueError(f"unknown status {name!r}")
        if active_task is _KEEP_TASK:
            existing = state_module.load()
            task = existing.active_task if existing else None
        else:
            task = active_task
        current = ComputedState(status=name, source=source, active_task=task)
        results = self.apply(current)
        state_module.save(State(
            source=source,
            set_at=now_iso(),
            status=name,
            active_task=task,
        ))
        return results

    def apply_rgb(
        self, r: int, g: int, b: int, source: str = "manual"
    ) -> None:
        """RGB is intentionally not routed through sinks (Slack can't show
        an arbitrary colour). Hits the device directly and persists state."""
        if self._light is None:
            self._light = LuxaforFlag()
        self._light.static(r, g, b)
        state_module.save(State(
            source=source,
            set_at=now_iso(),
            rgb=(r, g, b),
        ))

    def close(self) -> None:
        for sink in self.sinks:
            try:
                sink.close()
            except Exception:
                pass

    def __enter__(self) -> "Controller":
        return self

    def __exit__(self, *args) -> None:
        self.close()
