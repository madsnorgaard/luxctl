"""systemd user-service install / uninstall.

Generates the unit on the fly with the correct ExecStart path (whichever
luxctl binary is actually being invoked), copies it to
~/.config/systemd/user/, daemon-reload, enable, start. Symmetric uninstall.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

UNIT_NAME = "luxctl.service"


def _user_unit_dir() -> Path:
    return Path.home() / ".config" / "systemd" / "user"


def _resolve_luxctl_binary() -> str:
    """Return the absolute path of the luxctl binary that should be in
    ExecStart. Defaults to the one that launched this process; falls back
    to whatever is on PATH; finally to a literal '%h/.local/bin/luxctl'."""
    argv0 = Path(sys.argv[0])
    if argv0.name == "luxctl" and argv0.exists():
        return str(argv0.resolve())
    found = shutil.which("luxctl")
    if found:
        return found
    return str(Path.home() / ".local" / "bin" / "luxctl")


def render_unit(exec_start: str | None = None) -> str:
    exec_path = exec_start or _resolve_luxctl_binary()
    return f"""[Unit]
Description=luxctl presence-aggregator daemon
After=graphical-session.target
PartOf=graphical-session.target

[Service]
Type=simple
ExecStart={exec_path} daemon
Restart=on-failure
RestartSec=5
StandardOutput=journal
StandardError=journal
Environment=LUXCTL_LOG=INFO

[Install]
WantedBy=graphical-session.target
"""


def _systemctl(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["systemctl", "--user", *args],
        capture_output=True,
        text=True,
    )


def _systemctl_available() -> bool:
    return shutil.which("systemctl") is not None


def install(exec_start: str | None = None, enable: bool = True, start: bool = True) -> int:
    unit_dir = _user_unit_dir()
    unit_dir.mkdir(parents=True, exist_ok=True)
    unit_path = unit_dir / UNIT_NAME
    unit_path.write_text(render_unit(exec_start=exec_start))
    print(f"luxctl: wrote {unit_path}")

    if not _systemctl_available():
        print("luxctl: systemctl not found, skipping enable/start.", file=sys.stderr)
        return 2

    r = _systemctl("daemon-reload")
    if r.returncode != 0:
        print(f"luxctl: daemon-reload failed: {r.stderr.strip()}", file=sys.stderr)
        return r.returncode

    if enable:
        action = "enable"
        if start:
            action = "enable --now"
        r = _systemctl(*action.split())
        if r.returncode != 0:
            print(f"luxctl: systemctl {action} failed: {r.stderr.strip()}", file=sys.stderr)
            return r.returncode
        print(f"luxctl: systemctl --user {action} {UNIT_NAME}")

    print("luxctl: tail logs with 'journalctl --user -fu luxctl.service'")
    return 0


def uninstall() -> int:
    if not _systemctl_available():
        print("luxctl: systemctl not found.", file=sys.stderr)
        return 2

    unit_path = _user_unit_dir() / UNIT_NAME
    if not unit_path.exists():
        print(f"luxctl: nothing to remove ({unit_path} not present)")
        return 0

    _systemctl("disable", "--now", UNIT_NAME)
    unit_path.unlink()
    _systemctl("daemon-reload")
    print(f"luxctl: removed {unit_path}, daemon disabled and stopped.")
    return 0


def status() -> int:
    """Print 'is the service installed/active?' compactly. No-op if no systemd."""
    unit_path = _user_unit_dir() / UNIT_NAME
    installed = unit_path.exists()
    print(f"unit file:  {'installed' if installed else 'not installed'} ({unit_path})")
    if not installed or not _systemctl_available():
        return 0
    r = _systemctl("is-active", UNIT_NAME)
    print(f"is-active:  {r.stdout.strip() or r.stderr.strip()}")
    r = _systemctl("is-enabled", UNIT_NAME)
    print(f"is-enabled: {r.stdout.strip() or r.stderr.strip()}")
    return 0
