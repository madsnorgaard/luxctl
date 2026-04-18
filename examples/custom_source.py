"""A complete worked example of a custom Source.

This source watches an environment variable, `LUXCTL_FORCE_STATUS`, and
forces the light to that status whenever the variable is set. Useful as
a low-effort kill switch in a shell script ("ssh box; export
LUXCTL_FORCE_STATUS=meeting; do work").

To use: drop this file into `luxctl/sources/env.py` and register it in
`luxctl/daemon.py:build_sources()`. See CONTRIBUTING.md.
"""

from __future__ import annotations

import os
from typing import Optional

from luxctl.sources import Source
from luxctl.types import Declaration


class EnvSource(Source):
    name = "env"
    priority = 50  # higher than slack so it really overrides

    def __init__(self, var: str = "LUXCTL_FORCE_STATUS"):
        self.var = var

    def current(self) -> Optional[Declaration]:
        value = os.environ.get(self.var)
        if not value:
            return None
        return Declaration(
            status=value,
            source=self.name,
            priority=self.priority,
            detail=f"${self.var}",
        )
