"""LogSink: append every transition to ~/.local/state/luxctl/log.jsonl.

A small auditable history of "what was the light at, when, why". Useful
both for debugging the daemon and for retrospective analysis ("how
much of this week was I marked as `meeting`?").
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict
from pathlib import Path
from typing import Optional

from .. import state as state_module
from ..types import ComputedState
from . import Sink


def _default_log_path() -> Path:
    xdg = os.environ.get("XDG_STATE_HOME") or str(Path.home() / ".local" / "state")
    return Path(xdg) / "luxctl" / "log.jsonl"


class LogSink(Sink):
    name = "log"

    def __init__(self, path: Optional[Path] = None) -> None:
        self.path = path or _default_log_path()

    def apply(self, current: ComputedState) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        record = {
            "at": state_module.now_iso(),
            **asdict(current),
        }
        with self.path.open("a") as f:
            f.write(json.dumps(record) + "\n")
