"""SlackSource: read your own Slack presence (active/away).

Polls `users.getPresence` (no user ID = current user). When Slack reports
`away`, declares 'brb' so the Luxafor reflects that you stepped away from
your computer in Slack's eyes (often diverges from the OS idle source).

Slack rate-limits at ~50 req/min for tier-3 methods; a 30s poll keeps us
well under that.
"""

from __future__ import annotations

import logging
import time
from typing import Optional

from ..types import Declaration
from . import Source

log = logging.getLogger("luxctl.slack")


class SlackSource(Source):
    name = "slack"
    priority = 40

    def __init__(
        self,
        token: str,
        away_status: str = "brb",
        poll_seconds: int = 30,
        client=None,  # injectable for tests
    ) -> None:
        if not token:
            raise ValueError("SlackSource requires a Slack user token (xoxp-…)")
        self.away_status = away_status
        self.poll_seconds = poll_seconds
        self._client = client
        if self._client is None:
            from slack_sdk import WebClient
            self._client = WebClient(token=token)
        self._cache_at: float = 0.0
        self._cache_presence: Optional[str] = None

    def _read_presence(self) -> Optional[str]:
        now = time.monotonic()
        if self._cache_presence and now - self._cache_at < self.poll_seconds:
            return self._cache_presence
        try:
            resp = self._client.users_getPresence()
        except Exception as exc:  # noqa: BLE001
            log.warning("users.getPresence failed: %s", exc)
            return self._cache_presence  # serve stale rather than going dark
        presence = resp.get("presence")
        self._cache_presence = presence
        self._cache_at = now
        return presence

    def current(self) -> Optional[Declaration]:
        presence = self._read_presence()
        if presence != "away":
            return None
        return Declaration(
            status=self.away_status,
            source=self.name,
            priority=self.priority,
            detail="Slack: away",
        )
