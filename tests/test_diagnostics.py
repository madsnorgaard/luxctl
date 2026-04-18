"""Tests for diagnostics. Real device probes are exercised against fakes."""

from __future__ import annotations

from luxctl.diagnostics import Check, first_failure_hint


def test_first_failure_hint_returns_first_failed():
    hint = first_failure_hint([
        Check("a", True),
        Check("b", False, hint="install thing"),
        Check("c", False, hint="other thing"),
    ])
    assert hint == "install thing"


def test_first_failure_hint_empty_when_all_pass():
    assert first_failure_hint([Check("a", True), Check("b", True)]) == ""


def test_first_failure_hint_skips_failures_without_hint():
    hint = first_failure_hint([
        Check("a", False, hint=""),
        Check("b", False, hint="real fix"),
    ])
    assert hint == "real fix"
