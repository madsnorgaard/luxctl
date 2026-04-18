"""Config + secrets loading.

Two TOML files at standard XDG paths:

  ~/.config/luxctl/config.toml   - non-sensitive: which sources/sinks
                                   are enabled, calendar URL, idle thresholds…
  ~/.config/luxctl/secrets.toml  - must be chmod 600. Slack tokens etc.

Both are optional. Missing files yield empty dicts; missing keys yield
sensible defaults.
"""

from __future__ import annotations

import os
import stat
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

if sys.version_info >= (3, 11):
    import tomllib
else:  # pragma: no cover
    import tomli as tomllib  # type: ignore[no-redef]


def _config_dir() -> Path:
    xdg = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    return Path(xdg) / "luxctl"


def config_path() -> Path:
    return _config_dir() / "config.toml"


def secrets_path() -> Path:
    return _config_dir() / "secrets.toml"


class ConfigError(RuntimeError):
    pass


def load_toml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("rb") as f:
        return tomllib.load(f)


def load_config(path: Path | None = None) -> dict[str, Any]:
    return load_toml(path or config_path())


def load_secrets(path: Path | None = None) -> dict[str, Any]:
    """Load secrets.toml after enforcing chmod 600 on Unix."""
    p = path or secrets_path()
    if not p.exists():
        return {}
    if os.name == "posix":
        mode = p.stat().st_mode
        if mode & (stat.S_IRGRP | stat.S_IWGRP | stat.S_IROTH | stat.S_IWOTH):
            raise ConfigError(
                f"{p} is readable by group/other. Run: chmod 600 {p}"
            )
    return load_toml(p)


def write_secrets(data: dict[str, Any], path: Path | None = None) -> Path:
    """Write secrets.toml atomically with chmod 600."""
    p = path or secrets_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    body = _to_toml(data)
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(body)
    if os.name == "posix":
        os.chmod(tmp, 0o600)
    tmp.replace(p)
    return p


def _to_toml(data: dict[str, Any]) -> str:
    """A tiny TOML serializer covering only what we write (string values
    nested one level deep). Avoids pulling in tomli-w."""
    lines: list[str] = []
    # Top-level scalars first.
    for key, value in data.items():
        if not isinstance(value, dict):
            lines.append(f"{key} = {_render(value)}")
    for section, block in data.items():
        if not isinstance(block, dict):
            continue
        lines.append("")
        lines.append(f"[{section}]")
        for key, value in block.items():
            lines.append(f"{key} = {_render(value)}")
    return "\n".join(lines) + "\n"


def _render(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, str):
        # TOML basic string with minimal escaping.
        escaped = value.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'
    raise TypeError(f"unsupported TOML value: {value!r}")


# --- Domain accessors with defaults --------------------------------------

@dataclass
class IdleConfig:
    enabled: bool = True
    away_minutes: int = 5
    offline_minutes: int = 30


@dataclass
class LockConfig:
    enabled: bool = True


@dataclass
class CalendarConfig:
    enabled: bool = False
    url: str | None = None
    cache_seconds: int = 60


@dataclass
class SlackConfig:
    enabled: bool = False
    poll_seconds: int = 30
    set_dnd_for: list[str] = field(default_factory=lambda: ["stressed", "dnd"])
    emoji_map: dict[str, str] = field(default_factory=dict)


@dataclass
class DaemonConfig:
    tick_seconds: float = 5.0


@dataclass
class Config:
    daemon: DaemonConfig
    idle: IdleConfig
    lock: LockConfig
    calendar: CalendarConfig
    slack: SlackConfig


def parse(raw: dict[str, Any]) -> Config:
    def section(name: str) -> dict[str, Any]:
        return raw.get(name, {}) if isinstance(raw.get(name, {}), dict) else {}

    daemon_d = section("daemon")
    idle_d = section("idle")
    lock_d = section("lock")
    cal_d = section("calendar")
    slack_d = section("slack")

    return Config(
        daemon=DaemonConfig(tick_seconds=float(daemon_d.get("tick_seconds", 5.0))),
        idle=IdleConfig(
            enabled=bool(idle_d.get("enabled", True)),
            away_minutes=int(idle_d.get("away_minutes", 5)),
            offline_minutes=int(idle_d.get("offline_minutes", 30)),
        ),
        lock=LockConfig(enabled=bool(lock_d.get("enabled", True))),
        calendar=CalendarConfig(
            enabled=bool(cal_d.get("enabled", False)),
            url=cal_d.get("url"),
            cache_seconds=int(cal_d.get("cache_seconds", 60)),
        ),
        slack=SlackConfig(
            enabled=bool(slack_d.get("enabled", False)),
            poll_seconds=int(slack_d.get("poll_seconds", 30)),
            set_dnd_for=list(slack_d.get("set_dnd_for", ["stressed", "dnd"])),
            emoji_map=dict(slack_d.get("emoji_map", {})),
        ),
    )
