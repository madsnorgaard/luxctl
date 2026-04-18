"""Low-level wrapper around the Luxafor Flag USB HID protocol.

The Flag accepts 8-byte command payloads. On Linux/hidraw the write must
also be prefixed with a report-ID byte (0x00 for this device), so the
on-the-wire packet is 9 bytes total.

Protocol reference: https://luxafor.com/hid-flag-api/
"""

from __future__ import annotations

import hid

VENDOR_ID = 0x04D8
PRODUCT_ID = 0xF372

MODE_STATIC = 0x01
MODE_FADE = 0x02
MODE_STROBE = 0x03
MODE_WAVE = 0x04
MODE_PATTERN = 0x06

LED_ALL = 0xFF
LED_FRONT = 0x41
LED_BACK = 0x42

PATTERN_LUXAFOR = 1
PATTERN_RANDOM_1 = 2
PATTERN_RANDOM_2 = 3
PATTERN_RANDOM_3 = 4
PATTERN_POLICE = 5
PATTERN_RANDOM_4 = 6
PATTERN_RANDOM_5 = 7
PATTERN_RAINBOW = 8

REPORT_ID = 0x00
PAYLOAD_LENGTH = 8


class LuxaforError(RuntimeError):
    """Raised when the device cannot be reached or written to."""


def _clamp_byte(value: int, name: str) -> int:
    if not 0 <= value <= 255:
        raise ValueError(f"{name} must be 0-255, got {value}")
    return value


class LuxaforFlag:
    """A minimal, explicit Luxafor Flag driver."""

    def __init__(self, device=None) -> None:
        if device is not None:
            self._device = device
            return
        try:
            self._device = hid.Device(vid=VENDOR_ID, pid=PRODUCT_ID)
        except (OSError, IOError, hid.HIDException) as exc:
            raise LuxaforError(
                "Cannot open Luxafor Flag (04d8:f372). Is it plugged in, "
                "and is the udev rule installed? See the README."
            ) from exc

    def _write(self, payload: list[int]) -> None:
        body = list(payload) + [0x00] * (PAYLOAD_LENGTH - len(payload))
        self._device.write(bytes([REPORT_ID, *body[:PAYLOAD_LENGTH]]))

    def static(self, r: int, g: int, b: int, led: int = LED_ALL) -> None:
        """Solid colour, no animation."""
        _clamp_byte(r, "r")
        _clamp_byte(g, "g")
        _clamp_byte(b, "b")
        self._write([MODE_STATIC, led, r, g, b])

    def fade(
        self, r: int, g: int, b: int, led: int = LED_ALL, speed: int = 30
    ) -> None:
        """Fade from current colour to target at the given speed."""
        self._write([MODE_FADE, led, r, g, b, speed])

    def strobe(
        self,
        r: int,
        g: int,
        b: int,
        led: int = LED_ALL,
        speed: int = 20,
        repeat: int = 5,
    ) -> None:
        """Strobe a colour `repeat` times at the given speed."""
        self._write([MODE_STROBE, led, r, g, b, speed, 0x00, repeat])

    def wave(
        self,
        r: int,
        g: int,
        b: int,
        wave_type: int = 1,
        speed: int = 30,
        repeat: int = 3,
    ) -> None:
        """Wave animation across the LEDs. wave_type is 1-5."""
        self._write([MODE_WAVE, wave_type, r, g, b, 0x00, repeat, speed])

    def pattern(self, pattern_id: int, repeat: int = 5) -> None:
        """Built-in pattern (1-8). Pattern 5 is the police siren."""
        if not 1 <= pattern_id <= 8:
            raise ValueError(f"pattern_id must be 1-8, got {pattern_id}")
        self._write([MODE_PATTERN, pattern_id, repeat])

    def off(self) -> None:
        self.static(0, 0, 0)

    def close(self) -> None:
        self._device.close()

    def __enter__(self) -> "LuxaforFlag":
        return self

    def __exit__(self, *args) -> None:
        self.close()
