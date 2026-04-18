"""Tests for config + secrets loading."""

from __future__ import annotations

import os
import stat
from pathlib import Path

import pytest

from luxctl import config as config_module
from luxctl.config import (
    ConfigError,
    load_config,
    load_secrets,
    parse,
    write_secrets,
)


def test_load_config_returns_empty_dict_when_missing(tmp_path):
    assert load_config(tmp_path / "nope.toml") == {}


def test_load_config_parses_toml(tmp_path):
    p = tmp_path / "config.toml"
    p.write_text("""
[idle]
enabled = true
away_minutes = 7

[slack]
enabled = false
""")
    cfg = load_config(p)
    assert cfg["idle"]["away_minutes"] == 7
    assert cfg["slack"]["enabled"] is False


def test_parse_applies_defaults():
    cfg = parse({})
    assert cfg.idle.away_minutes == 5
    assert cfg.idle.offline_minutes == 30
    assert cfg.calendar.enabled is False
    assert cfg.slack.set_dnd_for == ["stressed", "dnd"]


def test_parse_honours_overrides():
    cfg = parse({
        "idle": {"away_minutes": 15},
        "slack": {"set_dnd_for": ["on-fire"], "emoji_map": {"busy": ":lock:"}},
    })
    assert cfg.idle.away_minutes == 15
    assert cfg.slack.set_dnd_for == ["on-fire"]
    assert cfg.slack.emoji_map["busy"] == ":lock:"


def test_load_secrets_returns_empty_when_missing(tmp_path):
    assert load_secrets(tmp_path / "nope.toml") == {}


def test_load_secrets_rejects_world_readable(tmp_path):
    p = tmp_path / "secrets.toml"
    p.write_text("[slack]\ntoken = \"xoxp-fake\"\n")
    os.chmod(p, 0o644)
    with pytest.raises(ConfigError):
        load_secrets(p)


def test_load_secrets_accepts_chmod_600(tmp_path):
    p = tmp_path / "secrets.toml"
    p.write_text("[slack]\ntoken = \"xoxp-fake\"\n")
    os.chmod(p, 0o600)
    secrets = load_secrets(p)
    assert secrets["slack"]["token"] == "xoxp-fake"


def test_write_secrets_sets_chmod_600(tmp_path):
    p = tmp_path / "secrets.toml"
    written = write_secrets({"slack": {"token": "xoxp-fake"}}, p)
    assert written == p
    mode = p.stat().st_mode & 0o777
    assert mode == 0o600
    # Round-trip:
    assert load_secrets(p)["slack"]["token"] == "xoxp-fake"


def test_write_secrets_escapes_quotes(tmp_path):
    p = tmp_path / "secrets.toml"
    write_secrets({"slack": {"token": 'has"quote'}}, p)
    assert load_secrets(p)["slack"]["token"] == 'has"quote'
