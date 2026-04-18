"""Tests for the daemon's tick logic. Async loop is exercised via run().

Slow real-time waits are avoided by using tick_seconds=0 and a fast event-loop.
"""

from __future__ import annotations

import asyncio
from typing import Optional

import pytest

from luxctl import state as state_module
from luxctl.controller import Controller
from luxctl.daemon import Daemon, build_sinks, build_sources, compose
from luxctl.config import parse
from luxctl.sinks import Sink
from luxctl.sources import Source
from luxctl.state import State
from luxctl.types import ComputedState, Declaration


class FakeSink(Sink):
    def __init__(self, name="fake", fail=False):
        self.name = name
        self.fail = fail
        self.applied: list[ComputedState] = []

    def apply(self, current: ComputedState) -> None:
        if self.fail:
            raise RuntimeError("boom")
        self.applied.append(current)


class FixedSource(Source):
    def __init__(self, name: str, priority: int, status: Optional[str], detail=None):
        self.name = name
        self.priority = priority
        self._status = status
        self._detail = detail

    def current(self) -> Optional[Declaration]:
        if self._status is None:
            return None
        return Declaration(
            status=self._status,
            source=self.name,
            priority=self.priority,
            detail=self._detail,
        )


@pytest.fixture(autouse=True)
def isolated_state(tmp_path, monkeypatch):
    monkeypatch.setattr("luxctl.state._default_path", lambda: tmp_path / "state.json")


def test_tick_applies_initial_state():
    sink = FakeSink()
    daemon = Daemon(
        sources=[FixedSource("calendar", 20, "meeting")],
        controller=Controller(sinks=[sink]),
    )
    applied = daemon.tick()
    assert applied is not None
    assert applied.status == "meeting"
    assert sink.applied[0].status == "meeting"


def test_tick_skips_when_state_unchanged():
    sink = FakeSink()
    daemon = Daemon(
        sources=[FixedSource("calendar", 20, "meeting")],
        controller=Controller(sinks=[sink]),
    )
    daemon.tick()
    daemon.tick()
    daemon.tick()
    assert len(sink.applied) == 1


def test_tick_reapplies_when_source_changes():
    src = FixedSource("calendar", 20, "meeting")
    sink = FakeSink()
    daemon = Daemon(sources=[src], controller=Controller(sinks=[sink]))
    daemon.tick()
    src._status = "available"
    daemon.tick()
    assert len(sink.applied) == 2
    assert sink.applied[1].status == "available"


def test_tick_falls_back_when_no_source_declares():
    sink = FakeSink()
    daemon = Daemon(
        sources=[FixedSource("manual", 0, None)],
        controller=Controller(sinks=[sink]),
        fallback_status="available",
    )
    applied = daemon.tick()
    assert applied.status == "available"
    assert applied.source == "default"


def test_tick_isolates_sink_failures():
    good = FakeSink("good")
    bad = FakeSink("bad", fail=True)
    daemon = Daemon(
        sources=[FixedSource("manual", 0, "busy")],
        controller=Controller(sinks=[bad, good]),
    )
    daemon.tick()  # should not raise
    assert good.applied[0].status == "busy"


def test_compose_attaches_persisted_active_task(tmp_path):
    state_module.save(State(
        source="cli", set_at="2026-04-18T15:00:00+00:00",
        status="busy", active_task="Drupal migration",
    ))
    decl = Declaration(status="meeting", source="calendar", priority=20)
    cs = compose(decl)
    assert cs.status == "meeting"
    assert cs.active_task == "Drupal migration"


def test_run_exits_on_stop():
    sink = FakeSink()
    daemon = Daemon(
        sources=[FixedSource("manual", 0, "busy")],
        controller=Controller(sinks=[sink]),
        tick_seconds=0.01,
    )

    async def runner():
        task = asyncio.create_task(daemon.run())
        await asyncio.sleep(0.05)
        daemon.stop()
        await task

    asyncio.run(runner())
    assert sink.applied  # at least one tick happened


def test_build_sources_default_includes_manual_idle_lock():
    cfg = parse({})
    srcs = build_sources(cfg, secrets={})
    names = [s.name for s in srcs]
    assert "manual" in names
    assert "idle" in names
    assert "lock" in names


def test_build_sources_skips_calendar_without_url():
    cfg = parse({"calendar": {"enabled": True}})
    srcs = build_sources(cfg, secrets={})
    assert "calendar" not in [s.name for s in srcs]


def test_build_sinks_default_is_luxafor_and_log(monkeypatch):
    # LuxaforSink will try to open the device — patch it out.
    from luxctl import sinks
    class FakeLuxaforSink:
        name = "luxafor"
        def apply(self, x): pass
        def close(self): pass
    monkeypatch.setattr(sinks, "LuxaforSink", lambda: FakeLuxaforSink())
    monkeypatch.setattr("luxctl.daemon.LuxaforSink", lambda: FakeLuxaforSink())

    cfg = parse({})
    sinks_built = build_sinks(cfg, secrets={})
    names = [s.name for s in sinks_built]
    assert "luxafor" in names
    assert "log" in names
