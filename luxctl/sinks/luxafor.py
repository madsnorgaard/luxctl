"""LuxaforSink: drives the physical Luxafor Flag.

Reuses an existing open device handle (Controller-owned) when given,
or opens its own. The daemon shares one handle to avoid re-opening on
every transition.
"""

from __future__ import annotations

from typing import Optional

from ..device import LuxaforError, LuxaforFlag
from ..statuses import STATUSES
from ..types import ComputedState
from . import Sink


class LuxaforSink(Sink):
    name = "luxafor"

    def __init__(self, light: Optional[LuxaforFlag] = None) -> None:
        self._owns_light = light is None
        self._light = light or LuxaforFlag()

    def apply(self, current: ComputedState) -> None:
        fn = STATUSES.get(current.status)
        if fn is None:
            raise LuxaforError(f"unknown status {current.status!r}")
        fn(self._light)

    def close(self) -> None:
        if self._owns_light:
            self._light.close()
