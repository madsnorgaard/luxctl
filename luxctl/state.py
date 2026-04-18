"""Persisted current state of the light.

Stored at ~/.config/luxctl/state.json so the tray (and any future daemon)
can answer "what is the light currently set to, by whom, and when?".
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
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
    """

    source: str
    set_at: str
    status: Optional[str] = None
    rgb: Optional[tuple[int, int, int]] = None

    def describe(self) -> str:
        what = self.status if self.status else (
            f"rgb({self.rgb[0]},{self.rgb[1]},{self.rgb[2]})" if self.rgb else "?"
        )
        return f"{what} (via {self.source} at {self.set_at})"


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
    )


def save(state: State, path: Optional[Path] = None) -> None:
    path = path or _default_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = asdict(state)
    if payload.get("rgb") is not None:
        payload["rgb"] = list(payload["rgb"])
    path.write_text(json.dumps(payload, indent=2) + "\n")


def clear(path: Optional[Path] = None) -> None:
    path = path or _default_path()
    try:
        path.unlink()
    except FileNotFoundError:
        pass
