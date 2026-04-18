"""Persisted current state of the light + active task.

Stored at ~/.config/luxctl/state.json so the tray, the daemon, and any
ad-hoc script can answer "what is the light currently set to, by whom,
when, and what task is the user working on?".
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


def _default_path() -> Path:
    xdg = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    return Path(xdg) / "luxctl" / "state.json"


@dataclass
class State:
    """The most recent intentional state applied to the light.

    Exactly one of `status` (a preset name) or `rgb` (a 3-tuple) is set.
    `source` identifies who set it (e.g. "manual", "calendar", "slack").
    `set_at` is an ISO-8601 UTC timestamp.
    `active_task` is free-form text the user is working on, plumbed into
    e.g. Slack `status_text` by the SlackSink.
    """

    source: str
    set_at: str
    status: Optional[str] = None
    rgb: Optional[tuple[int, int, int]] = None
    active_task: Optional[str] = None

    def describe(self) -> str:
        what = self.status if self.status else (
            f"rgb({self.rgb[0]},{self.rgb[1]},{self.rgb[2]})" if self.rgb else "?"
        )
        task = f" — task: {self.active_task!r}" if self.active_task else ""
        return f"{what} (via {self.source} at {self.set_at}){task}"


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def load(path: Optional[Path] = None) -> Optional[State]:
    path = path or _default_path()
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return None
    rgb = data.get("rgb")
    return State(
        source=data["source"],
        set_at=data["set_at"],
        status=data.get("status"),
        rgb=tuple(rgb) if rgb else None,
        active_task=data.get("active_task"),
    )


def save(state: State, path: Optional[Path] = None) -> None:
    path = path or _default_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = asdict(state)
    if payload.get("rgb") is not None:
        payload["rgb"] = list(payload["rgb"])
    path.write_text(json.dumps(payload, indent=2) + "\n")


def update(path: Optional[Path] = None, **changes) -> State:
    """Read current state, apply field changes, write it back. Used to
    set the active_task without touching status, etc."""
    s = load(path)
    if s is None:
        s = State(source="manual", set_at=now_iso())
    for k, v in changes.items():
        setattr(s, k, v)
    s.set_at = now_iso()
    save(s, path)
    return s


def clear(path: Optional[Path] = None) -> None:
    path = path or _default_path()
    try:
        path.unlink()
    except FileNotFoundError:
        pass
