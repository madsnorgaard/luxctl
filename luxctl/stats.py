"""'luxctl stats': summarise time spent per status from the transition log.

Reads ~/.local/state/luxctl/log.jsonl (the LogSink output), pairs each
transition with the next one to compute durations, and prints a small
table for 'today', 'this week', or a custom day count.

Pure stdlib. Tolerates a missing or malformed log gracefully.
"""

from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterator, Optional

from .sinks.log import _default_log_path


def _parse_iso(s: str) -> Optional[datetime]:
    try:
        return datetime.fromisoformat(s)
    except (TypeError, ValueError):
        return None


def _records(path: Path) -> Iterator[dict]:
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            yield json.loads(line)
        except json.JSONDecodeError:
            continue


def aggregate(path: Path, since: datetime, until: datetime) -> dict[str, timedelta]:
    """Return {status: total duration} between since/until.

    Each record is treated as 'this status started at record["at"] and
    lasted until the next record (or `until` if it is the last)'.
    """
    items: list[tuple[datetime, str]] = []
    for rec in _records(path):
        at = _parse_iso(rec.get("at", ""))
        status = rec.get("status")
        if at is None or not status:
            continue
        items.append((at, status))
    items.sort(key=lambda x: x[0])

    totals: dict[str, timedelta] = defaultdict(timedelta)
    for i, (at, status) in enumerate(items):
        end = items[i + 1][0] if i + 1 < len(items) else until
        start = max(at, since)
        finish = min(end, until)
        if finish > start:
            totals[status] += finish - start
    return dict(totals)


def _fmt(d: timedelta) -> str:
    total = int(d.total_seconds())
    h, rem = divmod(total, 3600)
    m, _ = divmod(rem, 60)
    if h:
        return f"{h}h{m:02d}m"
    return f"{m}m"


def run(period: str = "today", days: int = 0) -> int:
    now = datetime.now(timezone.utc)
    if days > 0:
        since = now - timedelta(days=days)
        label = f"last {days} days"
    elif period == "week":
        since = now - timedelta(days=7)
        label = "last 7 days"
    else:  # today
        local = datetime.now().astimezone()
        since = local.replace(hour=0, minute=0, second=0, microsecond=0).astimezone(timezone.utc)
        label = "today"

    path = _default_log_path()
    totals = aggregate(path, since=since, until=now)
    if not totals:
        print(f"luxctl stats ({label}): no data yet at {path}")
        return 0

    width = max(len(s) for s in totals) + 2
    print(f"luxctl stats ({label}):")
    total = sum(totals.values(), start=timedelta())
    for status, d in sorted(totals.items(), key=lambda kv: kv[1], reverse=True):
        pct = (d.total_seconds() / total.total_seconds() * 100) if total.total_seconds() else 0
        print(f"  {status:<{width}}{_fmt(d):>8}  {pct:5.1f}%")
    print(f"  {'TOTAL':<{width}}{_fmt(total):>8}")
    return 0
