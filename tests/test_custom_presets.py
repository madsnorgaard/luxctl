"""Tests for [presets.*] config-driven custom presets."""

from __future__ import annotations

import pytest

from luxctl.device import LuxaforFlag, MODE_PATTERN, MODE_STATIC, MODE_STROBE
from luxctl.statuses import STATUSES, load_from_config


@pytest.fixture(autouse=True)
def restore_statuses():
    snapshot = dict(STATUSES)
    yield
    STATUSES.clear()
    STATUSES.update(snapshot)


def test_static_preset(fake_hid):
    load_from_config({"focus": {"static": [10, 20, 30], "description": "focus mode"}})
    light = LuxaforFlag(device=fake_hid)
    STATUSES["focus"](light)
    payload = fake_hid.writes[0][1:]
    assert payload[0] == MODE_STATIC
    assert payload[2:5] == bytes([10, 20, 30])
    assert STATUSES["focus"].description == "focus mode"


def test_strobe_preset_with_modifiers(fake_hid):
    load_from_config({"alarm": {"strobe": [255, 0, 0], "speed": 5, "repeat": 7}})
    light = LuxaforFlag(device=fake_hid)
    STATUSES["alarm"](light)
    payload = fake_hid.writes[0][1:]
    assert payload[0] == MODE_STROBE
    assert payload[5] == 5
    assert payload[7] == 7


def test_pattern_preset(fake_hid):
    load_from_config({"siren": {"pattern": 5, "repeat": 3}})
    light = LuxaforFlag(device=fake_hid)
    STATUSES["siren"](light)
    payload = fake_hid.writes[0][1:]
    assert payload[0] == MODE_PATTERN
    assert payload[1] == 5


def test_overrides_built_in(fake_hid):
    load_from_config({"available": {"static": [128, 128, 128]}})
    light = LuxaforFlag(device=fake_hid)
    STATUSES["available"](light)
    payload = fake_hid.writes[0][1:]
    assert payload[2:5] == bytes([128, 128, 128])


def test_returns_list_of_registered_names():
    names = load_from_config({"a": {"static": [1, 2, 3]}, "b": {"fade": [4, 5, 6]}})
    assert set(names) == {"a", "b"}


def test_skips_invalid_specs():
    names = load_from_config({"good": {"static": [1, 2, 3]}, "bad": {"nonsense": True}})
    assert names == ["good"]
