"""Tests for the CLI."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from luxctl import cli
from luxctl import state as state_module
from luxctl.controller import Controller
from luxctl.device import LuxaforFlag
from luxctl.sinks import LuxaforSink


@pytest.fixture(autouse=True)
def isolated_state(tmp_path, monkeypatch):
    monkeypatch.setattr("luxctl.state._default_path", lambda: tmp_path / "state.json")
    return tmp_path / "state.json"


def _patch_controller(fake_hid):
    """Return a context manager that swaps Controller for one wrapping fake_hid."""
    light = LuxaforFlag(device=fake_hid)
    fake_ctrl = Controller(sinks=[LuxaforSink(light=light)], light=light)
    return patch("luxctl.cli.Controller", return_value=fake_ctrl), fake_ctrl


def test_list_prints_all_presets(capsys):
    rc = cli.main(["list"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "available" in out
    assert "stressed" in out


def test_status_dispatches_through_controller(fake_hid):
    patcher, _ = _patch_controller(fake_hid)
    with patcher:
        rc = cli.main(["status", "stressed"])
    assert rc == 0
    assert fake_hid.writes
    # Default --source is now 'cli'
    assert state_module.load().source == "cli"


def test_status_with_explicit_source(fake_hid):
    patcher, _ = _patch_controller(fake_hid)
    with patcher:
        cli.main(["status", "meeting", "--source", "calendar"])
    s = state_module.load()
    assert s.source == "calendar"
    assert s.status == "meeting"


def test_status_with_task_flag_persists_task(fake_hid):
    patcher, _ = _patch_controller(fake_hid)
    with patcher:
        cli.main(["status", "busy", "--task", "Reviewing PR #42"])
    s = state_module.load()
    assert s.active_task == "Reviewing PR #42"
    assert s.status == "busy"


def test_status_without_task_flag_preserves_existing_task(fake_hid):
    state_module.update(active_task="Long-running task")
    patcher, _ = _patch_controller(fake_hid)
    with patcher:
        cli.main(["status", "meeting"])
    assert state_module.load().active_task == "Long-running task"


def test_rgb_passes_through_controller(fake_hid):
    patcher, _ = _patch_controller(fake_hid)
    with patcher:
        rc = cli.main(["rgb", "10", "20", "30"])
    assert rc == 0
    assert fake_hid.writes[0][3:6] == bytes([10, 20, 30])
    assert state_module.load().rgb == (10, 20, 30)


def test_off_persists_offline(fake_hid):
    patcher, _ = _patch_controller(fake_hid)
    with patcher:
        cli.main(["off"])
    s = state_module.load()
    assert s.status == "offline"


def test_unknown_status_is_rejected():
    with pytest.raises(SystemExit):
        cli.main(["status", "definitely-not-a-status"])


def test_no_command_errors():
    with pytest.raises(SystemExit):
        cli.main([])


def test_device_error_exits_nonzero(capsys):
    from luxctl.device import LuxaforError

    with patch("luxctl.cli.Controller", side_effect=LuxaforError("not plugged in")):
        rc = cli.main(["status", "available"])

    assert rc == 1
    assert "not plugged in" in capsys.readouterr().err


def test_version_flag(capsys):
    with pytest.raises(SystemExit) as exc:
        cli.main(["--version"])
    assert exc.value.code == 0
    assert "luxctl" in capsys.readouterr().out


def test_current_when_no_state(capsys):
    rc = cli.main(["current"])
    assert rc == 0
    assert "no state recorded" in capsys.readouterr().out


def test_current_after_status(fake_hid, capsys):
    patcher, _ = _patch_controller(fake_hid)
    with patcher:
        cli.main(["status", "stressed"])
    rc = cli.main(["current"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "stressed" in out


def test_task_set(capsys):
    rc = cli.main(["task", "Drupal migration"])
    assert rc == 0
    assert "Drupal migration" in capsys.readouterr().out
    assert state_module.load().active_task == "Drupal migration"


def test_task_clear(capsys):
    state_module.update(active_task="Something")
    rc = cli.main(["task", "--clear"])
    assert rc == 0
    assert state_module.load().active_task is None


def test_task_requires_text_or_clear():
    with pytest.raises(SystemExit):
        cli.main(["task"])
