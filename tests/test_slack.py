"""Tests for SlackSink + SlackSource (mocked WebClient)."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from luxctl.sinks.slack import DEFAULT_EMOJI_MAP, SlackSink
from luxctl.sources.slack import SlackSource
from luxctl.types import ComputedState


def make_sink(**kwargs):
    client = MagicMock()
    sink = SlackSink(token="xoxp-fake", client=client, **kwargs)
    return sink, client


# --- SlackSink ----------------------------------------------------------

def test_sink_sets_status_text_and_emoji():
    sink, client = make_sink()
    sink.apply(ComputedState(status="busy", source="manual"))
    client.users_profile_set.assert_called_once()
    profile = client.users_profile_set.call_args.kwargs["profile"]
    assert profile["status_emoji"] == DEFAULT_EMOJI_MAP["busy"]
    assert profile["status_text"]


def test_sink_uses_active_task_as_status_text():
    sink, client = make_sink()
    sink.apply(ComputedState(status="busy", source="manual", active_task="Code review"))
    profile = client.users_profile_set.call_args.kwargs["profile"]
    assert profile["status_text"] == "Code review"


def test_sink_falls_back_to_detail_then_status():
    sink, client = make_sink()
    sink.apply(ComputedState(status="meeting", source="calendar", detail="Standup"))
    profile = client.users_profile_set.call_args.kwargs["profile"]
    assert profile["status_text"] == "Standup"


def test_sink_truncates_status_text_at_100_chars():
    sink, client = make_sink()
    long = "x" * 150
    sink.apply(ComputedState(status="busy", source="manual", active_task=long))
    profile = client.users_profile_set.call_args.kwargs["profile"]
    assert len(profile["status_text"]) == 100


def test_sink_custom_emoji_map_overrides_default():
    sink, client = make_sink(emoji_map={"busy": ":lock:"})
    sink.apply(ComputedState(status="busy", source="manual"))
    profile = client.users_profile_set.call_args.kwargs["profile"]
    assert profile["status_emoji"] == ":lock:"


def test_sink_unknown_status_falls_back_to_neutral_emoji():
    sink, client = make_sink()
    sink.apply(ComputedState(status="custom", source="manual"))
    profile = client.users_profile_set.call_args.kwargs["profile"]
    assert profile["status_emoji"] == ":large_blue_circle:"


def test_sink_sets_dnd_when_status_is_in_dnd_list():
    sink, client = make_sink(set_dnd_for=["stressed"])
    sink.apply(ComputedState(status="stressed", source="manual"))
    client.dnd_setSnooze.assert_called_once_with(num_minutes=24 * 60)


def test_sink_does_not_resnooze_dnd_on_repeat():
    sink, client = make_sink(set_dnd_for=["stressed"])
    sink.apply(ComputedState(status="stressed", source="manual"))
    sink.apply(ComputedState(status="stressed", source="manual"))
    assert client.dnd_setSnooze.call_count == 1


def test_sink_ends_dnd_when_leaving_a_dnd_status():
    sink, client = make_sink(set_dnd_for=["stressed"])
    sink.apply(ComputedState(status="stressed", source="manual"))
    sink.apply(ComputedState(status="available", source="manual"))
    client.dnd_endSnooze.assert_called_once()


def test_sink_rejects_empty_token():
    with pytest.raises(ValueError):
        SlackSink(token="")


# --- SlackSource --------------------------------------------------------

def test_source_returns_none_when_active():
    client = MagicMock()
    client.users_getPresence.return_value = {"presence": "active"}
    src = SlackSource(token="xoxp-fake", client=client)
    assert src.current() is None


def test_source_declares_brb_when_away():
    client = MagicMock()
    client.users_getPresence.return_value = {"presence": "away"}
    src = SlackSource(token="xoxp-fake", client=client)
    decl = src.current()
    assert decl is not None
    assert decl.status == "brb"
    assert decl.source == "slack"


def test_source_caches_presence_within_poll_interval():
    client = MagicMock()
    client.users_getPresence.return_value = {"presence": "away"}
    src = SlackSource(token="xoxp-fake", client=client, poll_seconds=60)
    src.current()
    src.current()
    src.current()
    # Only one API call within the cache window.
    assert client.users_getPresence.call_count == 1


def test_source_serves_stale_data_on_api_error():
    client = MagicMock()
    client.users_getPresence.return_value = {"presence": "away"}
    src = SlackSource(token="xoxp-fake", client=client, poll_seconds=0)
    src.current()
    client.users_getPresence.side_effect = RuntimeError("rate limited")
    decl = src.current()
    assert decl is not None
    assert decl.status == "brb"


def test_source_priority_is_above_lock():
    from luxctl.sources import LockSource
    src = SlackSource(token="xoxp-fake", client=MagicMock())
    assert src.priority > LockSource().priority
