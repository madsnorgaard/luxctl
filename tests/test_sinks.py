"""Tests for sinks (LuxaforSink, LogSink) and the Sink abstract base."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from luxctl.device import LuxaforError, LuxaforFlag, MODE_PATTERN, MODE_STATIC, PATTERN_POLICE
from luxctl.sinks import LogSink, LuxaforSink
from luxctl.types import ComputedState


def test_luxafor_sink_applies_known_status(fake_hid):
    light = LuxaforFlag(device=fake_hid)
    sink = LuxaforSink(light=light)
    sink.apply(ComputedState(status="available", source="manual"))
    payload = fake_hid.writes[0][1:]
    assert payload[0] == MODE_STATIC
    assert payload[2:5] == bytes([0, 255, 0])


def test_luxafor_sink_applies_pattern_status(fake_hid):
    light = LuxaforFlag(device=fake_hid)
    sink = LuxaforSink(light=light)
    sink.apply(ComputedState(status="stressed", source="manual"))
    payload = fake_hid.writes[0][1:]
    assert payload[0] == MODE_PATTERN
    assert payload[1] == PATTERN_POLICE


def test_luxafor_sink_rejects_unknown_status(fake_hid):
    sink = LuxaforSink(light=LuxaforFlag(device=fake_hid))
    with pytest.raises(LuxaforError):
        sink.apply(ComputedState(status="not-a-real-status", source="manual"))


def test_luxafor_sink_close_does_not_close_borrowed_light(fake_hid):
    light = LuxaforFlag(device=fake_hid)
    sink = LuxaforSink(light=light)
    sink.close()
    # Borrowed light not closed; the daemon will own that lifecycle.
    assert fake_hid.closed is False


def test_log_sink_appends_jsonl(tmp_path: Path):
    log_path = tmp_path / "log.jsonl"
    sink = LogSink(path=log_path)
    sink.apply(ComputedState(status="busy", source="manual"))
    sink.apply(ComputedState(status="available", source="calendar", detail="Standup"))

    lines = log_path.read_text().splitlines()
    assert len(lines) == 2

    first = json.loads(lines[0])
    assert first["status"] == "busy"
    assert first["source"] == "manual"
    assert "at" in first

    second = json.loads(lines[1])
    assert second["status"] == "available"
    assert second["detail"] == "Standup"


def test_log_sink_creates_parent_dirs(tmp_path: Path):
    log_path = tmp_path / "deep" / "nested" / "log.jsonl"
    LogSink(path=log_path).apply(ComputedState(status="busy", source="manual"))
    assert log_path.exists()
