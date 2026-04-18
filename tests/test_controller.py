"""Tests for the Controller — apply state to multiple sinks at once."""

from __future__ import annotations

from pathlib import Path

import pytest

from luxctl import state as state_module
from luxctl.controller import Controller
from luxctl.device import LuxaforFlag
from luxctl.sinks import LogSink, LuxaforSink, Sink
from luxctl.types import ComputedState


class FakeSink(Sink):
    def __init__(self, name: str, fail: bool = False):
        self.name = name
        self.fail = fail
        self.applied: list[ComputedState] = []
        self.closed = False

    def apply(self, current: ComputedState) -> None:
        if self.fail:
            raise RuntimeError(f"{self.name} broke")
        self.applied.append(current)

    def close(self) -> None:
        self.closed = True


@pytest.fixture(autouse=True)
def isolated_state(tmp_path, monkeypatch):
    monkeypatch.setattr("luxctl.state._default_path", lambda: tmp_path / "state.json")
    return tmp_path


def test_apply_calls_every_sink():
    sinks = [FakeSink("a"), FakeSink("b")]
    ctrl = Controller(sinks=sinks)
    results = ctrl.apply(ComputedState(status="busy", source="manual"))
    assert all(err is None for _, err in results)
    assert sinks[0].applied[0].status == "busy"
    assert sinks[1].applied[0].status == "busy"


def test_apply_isolates_sink_failures():
    sinks = [FakeSink("a"), FakeSink("b", fail=True), FakeSink("c")]
    ctrl = Controller(sinks=sinks)
    results = ctrl.apply(ComputedState(status="busy", source="manual"))
    assert results[0][1] is None
    assert isinstance(results[1][1], RuntimeError)
    assert results[2][1] is None
    # The third sink still received the state despite the second one failing.
    assert sinks[2].applied[0].status == "busy"


def test_apply_status_persists_state(fake_hid, tmp_path):
    light = LuxaforFlag(device=fake_hid)
    ctrl = Controller(sinks=[LuxaforSink(light=light)])
    ctrl.apply_status("available", source="cli", active_task="Reading")

    s = state_module.load()
    assert s.status == "available"
    assert s.source == "cli"
    assert s.active_task == "Reading"


def test_apply_status_preserves_existing_task(fake_hid):
    light = LuxaforFlag(device=fake_hid)
    ctrl = Controller(sinks=[LuxaforSink(light=light)])
    ctrl.apply_status("busy", source="cli", active_task="Writing tests")
    # Now apply a different status without specifying task — task should persist.
    ctrl.apply_status("meeting", source="cli")
    assert state_module.load().active_task == "Writing tests"


def test_apply_status_can_explicitly_clear_task(fake_hid):
    light = LuxaforFlag(device=fake_hid)
    ctrl = Controller(sinks=[LuxaforSink(light=light)])
    ctrl.apply_status("busy", source="cli", active_task="Writing tests")
    ctrl.apply_status("available", source="cli", active_task=None)
    assert state_module.load().active_task is None


def test_apply_status_validates_name(fake_hid):
    ctrl = Controller(sinks=[LuxaforSink(light=LuxaforFlag(device=fake_hid))])
    with pytest.raises(ValueError):
        ctrl.apply_status("not-a-status")


def test_apply_rgb_persists_rgb(fake_hid):
    ctrl = Controller(sinks=[], light=LuxaforFlag(device=fake_hid))
    ctrl.apply_rgb(100, 150, 200, source="cli")
    s = state_module.load()
    assert s.rgb == (100, 150, 200)


def test_close_propagates_to_sinks():
    sinks = [FakeSink("a"), FakeSink("b")]
    ctrl = Controller(sinks=sinks)
    ctrl.close()
    assert sinks[0].closed and sinks[1].closed


def test_context_manager_closes(fake_hid):
    sinks = [FakeSink("a")]
    with Controller(sinks=sinks) as ctrl:
        ctrl.apply(ComputedState(status="busy", source="manual"))
    assert sinks[0].closed
