"""Tests for 'luxctl stats'."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from luxctl.stats import aggregate


def _write_log(path: Path, records: list[tuple[datetime, str]]) -> None:
    with path.open("w") as f:
        for at, status in records:
            f.write(json.dumps({"at": at.isoformat(), "status": status, "source": "test"}) + "\n")


def test_aggregate_pairs_consecutive_records(tmp_path):
    p = tmp_path / "log.jsonl"
    base = datetime(2026, 4, 18, 9, 0, tzinfo=timezone.utc)
    _write_log(p, [
        (base, "available"),
        (base + timedelta(hours=1), "meeting"),
        (base + timedelta(hours=2), "available"),
    ])
    totals = aggregate(p, since=base, until=base + timedelta(hours=3))
    assert totals["available"] == timedelta(hours=2)  # 0-1h + 2-3h
    assert totals["meeting"] == timedelta(hours=1)


def test_aggregate_clips_to_window(tmp_path):
    p = tmp_path / "log.jsonl"
    base = datetime(2026, 4, 18, 9, 0, tzinfo=timezone.utc)
    _write_log(p, [(base, "busy")])
    totals = aggregate(
        p,
        since=base + timedelta(hours=1),
        until=base + timedelta(hours=3),
    )
    assert totals["busy"] == timedelta(hours=2)


def test_aggregate_handles_missing_log(tmp_path):
    totals = aggregate(
        tmp_path / "missing.jsonl",
        since=datetime(2026, 4, 18, tzinfo=timezone.utc),
        until=datetime(2026, 4, 19, tzinfo=timezone.utc),
    )
    assert totals == {}


def test_aggregate_skips_corrupt_lines(tmp_path):
    p = tmp_path / "log.jsonl"
    base = datetime(2026, 4, 18, 9, 0, tzinfo=timezone.utc)
    p.write_text(
        json.dumps({"at": base.isoformat(), "status": "busy", "source": "x"}) + "\n"
        + "not json at all\n"
        + json.dumps({"at": (base + timedelta(hours=1)).isoformat(), "status": "available", "source": "x"}) + "\n"
    )
    totals = aggregate(p, since=base, until=base + timedelta(hours=2))
    assert "busy" in totals
    assert "available" in totals
