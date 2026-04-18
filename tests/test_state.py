"""Tests for state persistence."""

from __future__ import annotations

from pathlib import Path

from luxctl import state as state_module
from luxctl.state import State


def test_save_then_load_round_trip(tmp_path: Path):
    path = tmp_path / "state.json"
    s = State(source="manual", set_at="2026-04-18T15:00:00+00:00", status="available")
    state_module.save(s, path)
    loaded = state_module.load(path)
    assert loaded == s


def test_load_returns_none_when_missing(tmp_path: Path):
    assert state_module.load(tmp_path / "nope.json") is None


def test_load_returns_none_on_corrupt_json(tmp_path: Path):
    path = tmp_path / "state.json"
    path.write_text("{not valid json")
    assert state_module.load(path) is None


def test_rgb_is_persisted_as_tuple(tmp_path: Path):
    path = tmp_path / "state.json"
    s = State(
        source="manual",
        set_at="2026-04-18T15:00:00+00:00",
        rgb=(10, 20, 30),
    )
    state_module.save(s, path)
    loaded = state_module.load(path)
    assert loaded.rgb == (10, 20, 30)


def test_clear_removes_file(tmp_path: Path):
    path = tmp_path / "state.json"
    state_module.save(
        State(source="manual", set_at="2026-04-18T15:00:00+00:00", status="busy"),
        path,
    )
    state_module.clear(path)
    assert not path.exists()


def test_clear_is_silent_when_missing(tmp_path: Path):
    state_module.clear(tmp_path / "nope.json")  # should not raise


def test_describe_shows_status_when_set():
    s = State(source="manual", set_at="2026-04-18T15:00:00+00:00", status="busy")
    text = s.describe()
    assert "busy" in text
    assert "manual" in text


def test_describe_shows_rgb_when_set():
    s = State(source="manual", set_at="2026-04-18T15:00:00+00:00", rgb=(1, 2, 3))
    assert "rgb(1,2,3)" in s.describe()


def test_now_iso_is_parseable():
    from datetime import datetime

    iso = state_module.now_iso()
    parsed = datetime.fromisoformat(iso)
    assert parsed.tzinfo is not None
