"""luxctl — drive a Luxafor Flag from Linux."""

from .device import LuxaforError, LuxaforFlag
from .statuses import STATUSES, register

__all__ = ["LuxaforError", "LuxaforFlag", "STATUSES", "register"]
__version__ = "0.1.0"
