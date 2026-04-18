"""'luxctl doctor': single command that audits the install end to end.

Prints one line per check, [ok] or [fail], with a fix-it hint on failures.
Exit code is 0 if everything passes, 1 otherwise.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from . import config as config_module
from . import service as service_module
from .diagnostics import Check, diagnose_device


def _ok(name: str, detail: str = "") -> Check:
    return Check(name, True, detail=detail)


def _fail(name: str, hint: str, detail: str = "") -> Check:
    return Check(name, False, detail=detail, hint=hint)


def _check_python_version() -> Check:
    v = sys.version_info
    if v >= (3, 10):
        return _ok(f"Python {v.major}.{v.minor}.{v.micro}")
    return _fail(
        f"Python {v.major}.{v.minor}.{v.micro}",
        hint="luxctl needs Python 3.10 or newer",
    )


def _check_config_file() -> list[Check]:
    p = config_module.config_path()
    if not p.exists():
        return [_fail(
            "config.toml present",
            hint=f"run 'luxctl init' to create a starter config at {p}",
        )]
    try:
        config_module.load_config(p)
    except Exception as exc:  # noqa: BLE001
        return [_fail(
            "config.toml parses",
            hint="check the TOML syntax",
            detail=str(exc),
        )]
    return [_ok(f"config.toml at {p}")]


def _check_secrets_file() -> list[Check]:
    p = config_module.secrets_path()
    if not p.exists():
        return [Check(
            "secrets.toml not configured",
            ok=True,
            detail="(skip; only needed if Slack is enabled)",
        )]
    try:
        secrets = config_module.load_secrets(p)
    except config_module.ConfigError as exc:
        return [_fail("secrets.toml permissions", hint=str(exc))]
    msg = f"secrets.toml at {p} (chmod ok"
    if secrets.get("slack", {}).get("token"):
        msg += ", slack token present"
    msg += ")"
    return [_ok(msg)]


def _check_optional_imports() -> list[Check]:
    out: list[Check] = []
    try:
        import gi  # noqa: F401
        out.append(_ok("PyGObject importable (tray)"))
    except ImportError:
        out.append(Check(
            "PyGObject not importable (tray will not run)",
            ok=True,
            hint="sudo apt install python3-gi gir1.2-ayatanaappindicator3-0.1",
        ))
    try:
        import icalendar  # noqa: F401
        out.append(_ok("icalendar importable (CalendarSource)"))
    except ImportError:
        out.append(Check(
            "icalendar not importable (CalendarSource disabled)",
            ok=True,
            hint="pip install 'luxctl[calendar]'",
        ))
    try:
        import slack_sdk  # noqa: F401
        out.append(_ok("slack_sdk importable (Slack source/sink)"))
    except ImportError:
        out.append(Check(
            "slack_sdk not importable (Slack disabled)",
            ok=True,
            hint="pip install 'luxctl[slack]'",
        ))
    return out


def _check_service() -> list[Check]:
    unit = service_module._user_unit_dir() / service_module.UNIT_NAME
    if not unit.exists():
        return [Check(
            "systemd user service installed",
            ok=True,
            hint="optional: 'luxctl install-service' to autostart the daemon",
        )]
    return [_ok(f"systemd user service at {unit}")]


def _format(check: Check) -> str:
    tag = "[ok]  " if check.ok else "[fail]"
    line = f"  {tag}  {check.name}"
    if check.detail:
        line += f"\n          {check.detail}"
    if not check.ok and check.hint:
        line += f"\n          fix: {check.hint}"
    return line


def run() -> int:
    print("luxctl doctor")
    print("=============")
    sections: list[tuple[str, list[Check]]] = [
        ("Environment", [_check_python_version()]),
        ("Device", diagnose_device()),
        ("Config", _check_config_file() + _check_secrets_file()),
        ("Optional integrations", _check_optional_imports()),
        ("Daemon", _check_service()),
    ]

    failures = 0
    for label, checks in sections:
        print(f"\n{label}:")
        for c in checks:
            print(_format(c))
            if not c.ok:
                failures += 1

    print()
    if failures:
        print(f"{failures} check(s) failed. Address the 'fix:' hints above.")
        return 1
    print("All checks passed.")
    return 0
