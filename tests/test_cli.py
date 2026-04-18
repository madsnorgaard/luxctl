"""Tests for the CLI."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from luxctl import cli
from luxctl import state as state_module


@pytest.fixture(autouse=True)
def isolated_state(tmp_path, monkeypatch):
    """Send every CLI test's state writes to a tmp file."""
    monkeypatch.setattr("luxctl.state._default_path", lambda: tmp_path / "state.json")
    return tmp_path / "state.json"


def test_list_prints_all_presets(capsys):
    rc = cli.main(["list"])
    captured = capsys.readouterr()
    assert rc == 0
    assert "available" in captured.out
    assert "stressed" in captured.out


def test_status_dispatches_to_device(fake_hid):
    with patch("luxctl.cli.LuxaforFlag") as flag_class:
        flag_class.return_value.__enter__.return_value.__class__ = type(fake_hid)
        # Use a real LuxaforFlag wrapping our fake device.
        from luxctl.device import LuxaforFlag

        real_light = LuxaforFlag(device=fake_hid)
        flag_class.return_value.__enter__.return_value = real_light
        flag_class.return_value.__exit__.return_value = None

        rc = cli.main(["status", "stressed"])

    assert rc == 0
    assert fake_hid.writes, "stressed status produced no HID write"


def test_rgb_passes_through_to_device(fake_hid):
    from luxctl.device import LuxaforFlag

    with patch("luxctl.cli.LuxaforFlag") as flag_class:
        flag_class.return_value.__enter__.return_value = LuxaforFlag(device=fake_hid)
        flag_class.return_value.__exit__.return_value = None
        rc = cli.main(["rgb", "10", "20", "30"])

    assert rc == 0
    # report = report-id + 8-byte payload; rgb lives at payload bytes 2..5
    assert fake_hid.writes[0][3:6] == bytes([10, 20, 30])


def test_off_command(fake_hid):
    from luxctl.device import LuxaforFlag

    with patch("luxctl.cli.LuxaforFlag") as flag_class:
        flag_class.return_value.__enter__.return_value = LuxaforFlag(device=fake_hid)
        flag_class.return_value.__exit__.return_value = None
        rc = cli.main(["off"])

    assert rc == 0
    assert fake_hid.writes[0][3:6] == bytes([0, 0, 0])


def test_unknown_status_is_rejected():
    with pytest.raises(SystemExit):
        cli.main(["status", "definitely-not-a-status"])


def test_no_command_errors():
    with pytest.raises(SystemExit):
        cli.main([])


def test_device_error_exits_nonzero(capsys):
    from luxctl.device import LuxaforError

    with patch("luxctl.cli.LuxaforFlag", side_effect=LuxaforError("not plugged in")):
        rc = cli.main(["status", "available"])

    captured = capsys.readouterr()
    assert rc == 1
    assert "not plugged in" in captured.err


def test_version_flag(capsys):
    with pytest.raises(SystemExit) as exc:
        cli.main(["--version"])
    assert exc.value.code == 0
    assert "luxctl" in capsys.readouterr().out


def test_status_persists_state(fake_hid, isolated_state):
    from luxctl.device import LuxaforFlag

    with patch("luxctl.cli.LuxaforFlag") as flag_class:
        flag_class.return_value.__enter__.return_value = LuxaforFlag(device=fake_hid)
        flag_class.return_value.__exit__.return_value = None
        cli.main(["status", "available"])

    s = state_module.load()
    assert s is not None
    assert s.status == "available"
    assert s.source == "manual"


def test_status_with_explicit_source(fake_hid, isolated_state):
    from luxctl.device import LuxaforFlag

    with patch("luxctl.cli.LuxaforFlag") as flag_class:
        flag_class.return_value.__enter__.return_value = LuxaforFlag(device=fake_hid)
        flag_class.return_value.__exit__.return_value = None
        cli.main(["status", "meeting", "--source", "calendar"])

    s = state_module.load()
    assert s.source == "calendar"
    assert s.status == "meeting"


def test_rgb_persists_state(fake_hid, isolated_state):
    from luxctl.device import LuxaforFlag

    with patch("luxctl.cli.LuxaforFlag") as flag_class:
        flag_class.return_value.__enter__.return_value = LuxaforFlag(device=fake_hid)
        flag_class.return_value.__exit__.return_value = None
        cli.main(["rgb", "10", "20", "30"])

    s = state_module.load()
    assert s.rgb == (10, 20, 30)
    assert s.status is None


def test_off_persists_offline_state(fake_hid, isolated_state):
    from luxctl.device import LuxaforFlag

    with patch("luxctl.cli.LuxaforFlag") as flag_class:
        flag_class.return_value.__enter__.return_value = LuxaforFlag(device=fake_hid)
        flag_class.return_value.__exit__.return_value = None
        cli.main(["off"])

    s = state_module.load()
    assert s.status == "offline"


def test_current_when_no_state(capsys):
    rc = cli.main(["current"])
    assert rc == 0
    assert "no state recorded" in capsys.readouterr().out


def test_current_after_status(fake_hid, capsys):
    from luxctl.device import LuxaforFlag

    with patch("luxctl.cli.LuxaforFlag") as flag_class:
        flag_class.return_value.__enter__.return_value = LuxaforFlag(device=fake_hid)
        flag_class.return_value.__exit__.return_value = None
        cli.main(["status", "stressed"])

    rc = cli.main(["current"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "stressed" in out
    assert "manual" in out
