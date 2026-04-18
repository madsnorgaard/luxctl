"""Tests for status presets."""

from __future__ import annotations

import pytest

from luxctl.device import MODE_PATTERN, MODE_STATIC, PATTERN_POLICE, REPORT_ID
from luxctl.statuses import STATUSES


def _payload(report: bytes) -> bytes:
    assert report[0] == REPORT_ID
    return report[1:]


def test_known_statuses_are_registered():
    expected = {
        "available",
        "busy",
        "meeting",
        "brb",
        "offline",
        "deep-work",
        "pairing",
        "rubber-duck",
        "deploying",
        "stressed",
        "on-fire",
        "coffee",
        "lunch",
        "kid-incoming",
        "party",
        "dnd",
    }
    assert expected.issubset(STATUSES.keys())


def test_every_status_has_a_description():
    for name, fn in STATUSES.items():
        desc = getattr(fn, "description", "")
        assert desc, f"{name} is missing a description"


@pytest.mark.parametrize("name", sorted(STATUSES))
def test_every_status_writes_to_device(name, light, fake_hid):
    STATUSES[name](light)
    assert fake_hid.writes, f"{name} did not write any HID report"


def test_stressed_triggers_police_pattern(light, fake_hid):
    STATUSES["stressed"](light)
    payload = _payload(fake_hid.writes[0])
    assert payload[0] == MODE_PATTERN
    assert payload[1] == PATTERN_POLICE


def test_available_is_solid_green(light, fake_hid):
    STATUSES["available"](light)
    payload = _payload(fake_hid.writes[0])
    assert payload[0] == MODE_STATIC
    assert payload[2:5] == bytes([0, 255, 0])


def test_offline_is_off(light, fake_hid):
    STATUSES["offline"](light)
    payload = _payload(fake_hid.writes[0])
    assert payload[0] == MODE_STATIC
    assert payload[2:5] == bytes([0, 0, 0])
