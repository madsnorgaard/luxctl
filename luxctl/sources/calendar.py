"""CalendarSource: read an iCal feed and declare 'meeting' during events.

Pass either:
- `url` - an HTTPS iCal feed (Google Calendar's "secret address in iCal
  format", Outlook published calendar, Fastmail, etc.). The URL is
  fetched on each `current()` call but the parsed result is cached for
  `cache_seconds` to avoid hammering the server.
- `path` - a local .ics file (handy for tests).

Recurring events are expanded with `recurring-ical-events` if installed,
otherwise only non-recurring events are honoured (a clear log warning is
emitted in that case).
"""

from __future__ import annotations

import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Optional
from urllib.request import Request, urlopen

from ..types import Declaration
from . import Source

try:
    from icalendar import Calendar  # type: ignore[import-untyped]
    _HAVE_ICALENDAR = True
except ImportError:
    _HAVE_ICALENDAR = False

try:
    import recurring_ical_events  # type: ignore[import-untyped]
    _HAVE_RECURRING = True
except ImportError:
    _HAVE_RECURRING = False


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _ensure_aware(dt) -> datetime:
    """iCal `DATE` (no time) values come through as `date`, all-day events.
    Attach UTC to anything naive so comparisons work."""
    if isinstance(dt, datetime):
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt
    # `date` (all-day) - represent as midnight UTC
    return datetime(dt.year, dt.month, dt.day, tzinfo=timezone.utc)


def _fetch(url: str, timeout: float = 5.0) -> bytes:
    req = Request(url, headers={"User-Agent": "luxctl-calendar/1.0"})
    with urlopen(req, timeout=timeout) as resp:
        return resp.read()


class CalendarSource(Source):
    name = "calendar"
    priority = 20

    def __init__(
        self,
        url: Optional[str] = None,
        path: Optional[Path] = None,
        cache_seconds: int = 60,
        meeting_status: str = "meeting",
    ) -> None:
        if not _HAVE_ICALENDAR:
            raise ImportError(
                "CalendarSource requires the icalendar package. "
                "Install with: pip install 'luxctl[calendar]'"
            )
        if (url is None) == (path is None):
            raise ValueError("CalendarSource needs exactly one of url= or path=")
        self.url = url
        self.path = Path(path) if path else None
        self.cache_seconds = cache_seconds
        self.meeting_status = meeting_status
        self._cache_at: float = 0.0
        self._cache_bytes: bytes = b""

    def _load_bytes(self) -> bytes:
        now = time.monotonic()
        if self._cache_bytes and now - self._cache_at < self.cache_seconds:
            return self._cache_bytes
        if self.url:
            try:
                self._cache_bytes = _fetch(self.url)
            except Exception:
                # Keep serving stale data rather than going dark.
                if self._cache_bytes:
                    return self._cache_bytes
                raise
        else:
            assert self.path is not None
            self._cache_bytes = self.path.read_bytes()
        self._cache_at = now
        return self._cache_bytes

    def _expand_events(self, cal_bytes: bytes, now: datetime) -> Iterable:
        cal = Calendar.from_ical(cal_bytes)
        if _HAVE_RECURRING:
            # Look 1 minute either side of now - covers the active event(s).
            from datetime import timedelta
            return recurring_ical_events.of(cal).between(
                now - timedelta(minutes=1), now + timedelta(minutes=1)
            )
        # No recurrence support: enumerate raw VEVENTs (one-shot events only).
        return [c for c in cal.walk("VEVENT")]

    def current(self) -> Optional[Declaration]:
        try:
            data = self._load_bytes()
        except Exception:
            return None
        now = _now()
        for event in self._expand_events(data, now):
            try:
                start = _ensure_aware(event["DTSTART"].dt)
                end = _ensure_aware(event["DTEND"].dt) if "DTEND" in event else None
            except (KeyError, AttributeError):
                continue
            if end is None:
                continue
            if start <= now < end:
                title = str(event.get("SUMMARY", "")).strip() or None
                return Declaration(
                    status=self.meeting_status,
                    source=self.name,
                    priority=self.priority,
                    detail=title,
                )
        return None
