"""luxctl - drive a Luxafor Flag from Linux, plus a presence aggregator."""

from .device import LuxaforError, LuxaforFlag
from .statuses import STATUSES, register
from .types import ComputedState, Declaration

__all__ = [
    "LuxaforError",
    "LuxaforFlag",
    "STATUSES",
    "register",
    "ComputedState",
    "Declaration",
]
__version__ = "0.2.0"
