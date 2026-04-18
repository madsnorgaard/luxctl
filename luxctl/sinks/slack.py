"""SlackSink: writes the resolved status to your Slack profile.

For each ComputedState we set:
  - users.profile.set: status_text + status_emoji + status_expiration
  - dnd.setSnooze: when the status is in `set_dnd_for` (default: stressed, dnd)
  - dnd.endSnooze: when leaving such a status

`emoji_map` translates a luxctl status into a Slack emoji code. Anything
not in the map gets `:large_blue_circle:` as a neutral default.
"""

from __future__ import annotations

import logging
from typing import Optional

from ..types import ComputedState
from . import Sink

log = logging.getLogger("luxctl.slack")

DEFAULT_EMOJI_MAP: dict[str, str] = {
    "available": ":large_green_circle:",
    "busy": ":no_entry:",
    "meeting": ":calendar:",
    "brb": ":coffee:",
    "offline": ":zzz:",
    "deep-work": ":headphones:",
    "pairing": ":handshake:",
    "rubber-duck": ":duck:",
    "deploying": ":ship:",
    "stressed": ":rotating_light:",
    "on-fire": ":fire:",
    "coffee": ":coffee:",
    "lunch": ":sandwich:",
    "kid-incoming": ":baby:",
    "party": ":tada:",
    "dnd": ":no_bell:",
}


class SlackSink(Sink):
    name = "slack"

    def __init__(
        self,
        token: str,
        emoji_map: Optional[dict[str, str]] = None,
        set_dnd_for: Optional[list[str]] = None,
        client=None,  # injectable for tests
    ) -> None:
        if not token:
            raise ValueError("SlackSink requires a Slack user token (xoxp-…)")
        self.emoji_map = {**DEFAULT_EMOJI_MAP, **(emoji_map or {})}
        self.set_dnd_for = set(set_dnd_for or ["stressed", "dnd"])
        self._client = client
        if self._client is None:
            from slack_sdk import WebClient
            self._client = WebClient(token=token)
        self._dnd_active = False

    def _emoji_for(self, status: str) -> str:
        return self.emoji_map.get(status, ":large_blue_circle:")

    def apply(self, current: ComputedState) -> None:
        text = current.display_text()
        emoji = self._emoji_for(current.status)
        # 0 means "no expiration".
        self._client.users_profile_set(profile={
            "status_text": text[:100],  # Slack hard-limit
            "status_emoji": emoji,
            "status_expiration": 0,
        })

        should_dnd = current.status in self.set_dnd_for
        if should_dnd and not self._dnd_active:
            # 24h is the maximum useful value; the daemon will end it
            # explicitly the moment the status flips.
            self._client.dnd_setSnooze(num_minutes=24 * 60)
            self._dnd_active = True
        elif not should_dnd and self._dnd_active:
            try:
                self._client.dnd_endSnooze()
            except Exception as exc:  # noqa: BLE001
                log.warning("dnd_endSnooze failed: %s", exc)
            self._dnd_active = False
