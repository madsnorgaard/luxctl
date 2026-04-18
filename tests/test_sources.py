"""Tests for the source resolution logic."""

from __future__ import annotations

from typing import Optional

from luxctl.sources import Declaration, ManualSource, Source, resolve


class FixedSource(Source):
    def __init__(self, name: str, priority: int, status: Optional[str]):
        self.name = name
        self.priority = priority
        self._status = status

    def current(self) -> Optional[Declaration]:
        if self._status is None:
            return None
        return Declaration(status=self._status, source=self.name, priority=self.priority)


def test_resolve_returns_none_when_all_idle():
    assert resolve([FixedSource("a", 0, None), FixedSource("b", 5, None)]) is None


def test_resolve_picks_highest_priority():
    decl = resolve(
        [
            FixedSource("calendar", 10, "meeting"),
            FixedSource("manual", 0, "available"),
        ]
    )
    assert decl is not None
    assert decl.status == "meeting"
    assert decl.source == "calendar"


def test_resolve_breaks_ties_by_first_position():
    decl = resolve(
        [
            FixedSource("a", 5, "available"),
            FixedSource("b", 5, "busy"),
        ]
    )
    assert decl.source == "a"


def test_manual_source_returns_none_without_state(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "luxctl.state._default_path", lambda: tmp_path / "state.json"
    )
    assert ManualSource().current() is None


def test_manual_source_reads_persisted_state(tmp_path, monkeypatch):
    from luxctl import state as state_module
    from luxctl.state import State

    path = tmp_path / "state.json"
    monkeypatch.setattr("luxctl.state._default_path", lambda: path)
    state_module.save(
        State(source="manual", set_at="2026-04-18T15:00:00+00:00", status="busy")
    )
    decl = ManualSource().current()
    assert decl is not None
    assert decl.status == "busy"
    assert decl.source == "manual"


def test_manual_source_ignores_state_from_another_source(tmp_path, monkeypatch):
    from luxctl import state as state_module
    from luxctl.state import State

    path = tmp_path / "state.json"
    monkeypatch.setattr("luxctl.state._default_path", lambda: path)
    state_module.save(
        State(source="calendar", set_at="2026-04-18T15:00:00+00:00", status="meeting")
    )
    assert ManualSource().current() is None
