"""Tests for IdleSource, LockSource, and CalendarSource."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from luxctl.sources import IdleSource, LockSource


# --- IdleSource ----------------------------------------------------------

def test_idle_source_returns_none_when_active():
    src = IdleSource(away_minutes=5, offline_minutes=30, idle_reader=lambda: 1_000)
    assert src.current() is None


def test_idle_source_declares_brb_after_threshold():
    src = IdleSource(away_minutes=5, offline_minutes=30, idle_reader=lambda: 6 * 60_000)
    decl = src.current()
    assert decl is not None
    assert decl.status == "brb"
    assert decl.source == "idle"
    assert "idle 6m" in decl.detail


def test_idle_source_declares_offline_after_long_idle():
    src = IdleSource(away_minutes=5, offline_minutes=30, idle_reader=lambda: 31 * 60_000)
    decl = src.current()
    assert decl is not None
    assert decl.status == "offline"


def test_idle_source_returns_none_when_reader_unavailable():
    src = IdleSource(idle_reader=lambda: None)
    assert src.current() is None


def test_idle_source_priority_is_above_manual():
    from luxctl.sources import ManualSource
    assert IdleSource().priority > ManualSource().priority


# --- LockSource ----------------------------------------------------------

def test_lock_source_returns_none_when_unlocked():
    src = LockSource(reader=lambda: False)
    assert src.current() is None


def test_lock_source_declares_offline_when_locked():
    src = LockSource(reader=lambda: True)
    decl = src.current()
    assert decl is not None
    assert decl.status == "offline"
    assert decl.source == "lock"


def test_lock_source_returns_none_when_reader_unavailable():
    src = LockSource(reader=lambda: None)
    assert src.current() is None


def test_lock_source_priority_is_above_calendar():
    from luxctl.sources import IdleSource
    assert LockSource().priority > IdleSource().priority


# --- CalendarSource ------------------------------------------------------

ICAL_TEMPLATE = """BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//luxctl-tests//
BEGIN:VEVENT
UID:test-event@luxctl
DTSTAMP:20260418T100000Z
DTSTART:{start}
DTEND:{end}
SUMMARY:{summary}
END:VEVENT
END:VCALENDAR
"""


def _ical(tmp_path: Path, start: datetime, end: datetime, summary: str) -> Path:
    fmt = "%Y%m%dT%H%M%SZ"
    p = tmp_path / "cal.ics"
    p.write_text(ICAL_TEMPLATE.format(
        start=start.strftime(fmt),
        end=end.strftime(fmt),
        summary=summary,
    ))
    return p


def test_calendar_source_declares_meeting_during_event(tmp_path):
    pytest.importorskip("icalendar")
    from luxctl.sources import CalendarSource

    now = datetime.now(timezone.utc)
    p = _ical(tmp_path, now - timedelta(minutes=15), now + timedelta(minutes=15), "Standup")
    src = CalendarSource(path=p)
    decl = src.current()
    assert decl is not None
    assert decl.status == "meeting"
    assert decl.source == "calendar"
    assert decl.detail == "Standup"


def test_calendar_source_returns_none_outside_event(tmp_path):
    pytest.importorskip("icalendar")
    from luxctl.sources import CalendarSource

    now = datetime.now(timezone.utc)
    p = _ical(tmp_path, now + timedelta(hours=2), now + timedelta(hours=3), "Future")
    src = CalendarSource(path=p)
    assert src.current() is None


def test_calendar_source_uses_cache_to_avoid_rereading(tmp_path):
    pytest.importorskip("icalendar")
    from luxctl.sources import CalendarSource

    now = datetime.now(timezone.utc)
    p = _ical(tmp_path, now - timedelta(minutes=5), now + timedelta(minutes=5), "Cached")
    src = CalendarSource(path=p, cache_seconds=60)
    src.current()  # primes cache
    p.write_bytes(b"")  # corrupt the file
    # Should still return the cached event, not crash.
    decl = src.current()
    assert decl is not None
    assert decl.detail == "Cached"


def test_calendar_source_rejects_both_url_and_path():
    pytest.importorskip("icalendar")
    from luxctl.sources import CalendarSource
    with pytest.raises(ValueError):
        CalendarSource(url="https://example.com/x.ics", path=Path("/tmp/x.ics"))


def test_calendar_source_rejects_neither_url_nor_path():
    pytest.importorskip("icalendar")
    from luxctl.sources import CalendarSource
    with pytest.raises(ValueError):
        CalendarSource()
