"""Tests for the LuxaforFlag wire protocol."""

from __future__ import annotations

import pytest

from luxctl.device import (
    LED_ALL,
    MODE_FADE,
    MODE_PATTERN,
    MODE_STATIC,
    MODE_STROBE,
    MODE_WAVE,
    PATTERN_POLICE,
    PATTERN_RAINBOW,
    PAYLOAD_LENGTH,
    REPORT_ID,
    LuxaforFlag,
)

# Wire packets are 1 report-ID byte + 8 payload bytes.
WIRE_LENGTH = 1 + PAYLOAD_LENGTH


def _payload(report: bytes) -> bytes:
    """Strip the leading report-ID byte and return the 8-byte payload."""
    assert report[0] == REPORT_ID
    return report[1:]


def test_static_writes_correct_report(light, fake_hid):
    light.static(255, 0, 128)
    assert len(fake_hid.writes) == 1
    report = fake_hid.writes[0]
    assert len(report) == WIRE_LENGTH
    payload = _payload(report)
    assert payload[0] == MODE_STATIC
    assert payload[1] == LED_ALL
    assert payload[2:5] == bytes([255, 0, 128])


def test_fade_includes_speed(light, fake_hid):
    light.fade(10, 20, 30, speed=42)
    payload = _payload(fake_hid.writes[0])
    assert payload[0] == MODE_FADE
    assert payload[2:5] == bytes([10, 20, 30])
    assert payload[5] == 42


def test_strobe_layout(light, fake_hid):
    light.strobe(255, 0, 0, speed=5, repeat=7)
    payload = _payload(fake_hid.writes[0])
    assert payload[0] == MODE_STROBE
    assert payload[2:5] == bytes([255, 0, 0])
    assert payload[5] == 5
    assert payload[7] == 7


def test_wave_layout(light, fake_hid):
    light.wave(0, 200, 200, wave_type=3, speed=15, repeat=4)
    payload = _payload(fake_hid.writes[0])
    assert payload[0] == MODE_WAVE
    assert payload[1] == 3
    assert payload[2:5] == bytes([0, 200, 200])
    assert payload[6] == 4
    assert payload[7] == 15


def test_pattern_police(light, fake_hid):
    light.pattern(PATTERN_POLICE, repeat=10)
    payload = _payload(fake_hid.writes[0])
    assert payload[0] == MODE_PATTERN
    assert payload[1] == PATTERN_POLICE
    assert payload[2] == 10


def test_pattern_rainbow(light, fake_hid):
    light.pattern(PATTERN_RAINBOW)
    payload = _payload(fake_hid.writes[0])
    assert payload[1] == PATTERN_RAINBOW


def test_pattern_validates_id(light):
    with pytest.raises(ValueError):
        light.pattern(0)
    with pytest.raises(ValueError):
        light.pattern(99)


def test_off_emits_black_static(light, fake_hid):
    light.off()
    payload = _payload(fake_hid.writes[0])
    assert payload[0] == MODE_STATIC
    assert payload[2:5] == bytes([0, 0, 0])


def test_static_validates_byte_range(light):
    with pytest.raises(ValueError):
        light.static(256, 0, 0)
    with pytest.raises(ValueError):
        light.static(-1, 0, 0)


def test_report_includes_report_id_and_payload(light, fake_hid):
    light.static(1, 2, 3)
    assert len(fake_hid.writes[0]) == WIRE_LENGTH
    assert fake_hid.writes[0][0] == REPORT_ID


def test_context_manager_closes_device(fake_hid):
    with LuxaforFlag(device=fake_hid) as light:
        light.static(1, 1, 1)
    assert fake_hid.closed is True
