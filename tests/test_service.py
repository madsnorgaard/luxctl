"""Tests for the systemd user-service install helpers."""

from __future__ import annotations

from luxctl import service as service_module


def test_render_unit_uses_provided_exec_path():
    unit = service_module.render_unit(exec_start="/opt/luxctl/bin/luxctl")
    assert "ExecStart=/opt/luxctl/bin/luxctl daemon" in unit
    assert "WantedBy=graphical-session.target" in unit


def test_render_unit_falls_back_to_resolved_binary(monkeypatch):
    monkeypatch.setattr(service_module, "_resolve_luxctl_binary", lambda: "/usr/local/bin/luxctl")
    unit = service_module.render_unit()
    assert "ExecStart=/usr/local/bin/luxctl daemon" in unit


def test_install_writes_unit_file(tmp_path, monkeypatch):
    monkeypatch.setattr(service_module, "_user_unit_dir", lambda: tmp_path)
    monkeypatch.setattr(service_module, "_systemctl_available", lambda: False)
    rc = service_module.install(exec_start="/x/luxctl")
    assert rc == 2  # systemctl unavailable, but unit was written
    assert (tmp_path / "luxctl.service").exists()
    assert "ExecStart=/x/luxctl daemon" in (tmp_path / "luxctl.service").read_text()


def test_uninstall_is_silent_when_not_installed(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(service_module, "_user_unit_dir", lambda: tmp_path)
    monkeypatch.setattr(service_module, "_systemctl_available", lambda: True)

    class FakeProc:
        returncode = 0
        stdout = ""
        stderr = ""
    monkeypatch.setattr(service_module, "_systemctl", lambda *a: FakeProc())

    rc = service_module.uninstall()
    assert rc == 0
    assert "nothing to remove" in capsys.readouterr().out
