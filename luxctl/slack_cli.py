"""`luxctl slack <subcommand>` - token setup, connectivity test, status push."""

from __future__ import annotations

import sys
from typing import Optional

from . import config as config_module


SETUP_INSTRUCTIONS = """\
To get a Slack user token (xoxp-...):

  1. Open https://api.slack.com/apps and click 'Create New App' → 'From scratch'.
  2. Pick a name (e.g. 'luxctl personal') and your workspace.
  3. In the left sidebar, choose 'OAuth & Permissions'.
  4. Under 'User Token Scopes', add:
        users.profile:write
        users:read
        dnd:read
        dnd:write
  5. Scroll up and click 'Install to Workspace', approve.
  6. Copy the 'User OAuth Token' that starts with 'xoxp-'.

Paste it below. It will be stored at ~/.config/luxctl/secrets.toml (chmod 600).
"""


def cmd_setup(_args) -> int:
    print(SETUP_INSTRUCTIONS)
    try:
        token = input("Slack user token: ").strip()
    except (EOFError, KeyboardInterrupt):
        print("\nluxctl: cancelled")
        return 1
    if not token.startswith("xoxp-"):
        print("luxctl: that does not look like a user token (xoxp-…)")
        return 2

    secrets = config_module.load_secrets() if config_module.secrets_path().exists() else {}
    secrets.setdefault("slack", {})["token"] = token
    path = config_module.write_secrets(secrets)
    print(f"luxctl: wrote {path} (chmod 600)")
    print("Run 'luxctl slack test' to verify, then enable the slack section in config.toml.")
    return 0


def cmd_test(_args) -> int:
    secrets = config_module.load_secrets()
    token = secrets.get("slack", {}).get("token")
    if not token:
        print("luxctl: no slack token. Run 'luxctl slack setup' first.", file=sys.stderr)
        return 1
    try:
        from slack_sdk import WebClient
        from slack_sdk.errors import SlackApiError
    except ImportError:
        print("luxctl: slack_sdk not installed. pip install 'luxctl[slack]'", file=sys.stderr)
        return 3
    client = WebClient(token=token)
    try:
        auth = client.auth_test()
    except SlackApiError as exc:
        print(f"luxctl: Slack rejected the token: {exc.response['error']}", file=sys.stderr)
        return 1
    print(f"OK - authed as {auth['user']} in workspace {auth['team']}")
    return 0


def cmd_push(args) -> int:
    """Manually push the current state to Slack (one-shot)."""
    from . import state as state_module
    from .types import ComputedState

    secrets = config_module.load_secrets()
    token = secrets.get("slack", {}).get("token")
    if not token:
        print("luxctl: no slack token. Run 'luxctl slack setup' first.", file=sys.stderr)
        return 1
    s = state_module.load()
    if s is None or s.status is None:
        print("luxctl: no current state to push", file=sys.stderr)
        return 1
    cfg = config_module.parse(config_module.load_config())
    from .sinks import SlackSink  # type: ignore[attr-defined]
    sink = SlackSink(
        token=token,
        emoji_map=cfg.slack.emoji_map,
        set_dnd_for=cfg.slack.set_dnd_for,
    )
    sink.apply(ComputedState(
        status=s.status,
        source=s.source,
        active_task=s.active_task,
    ))
    print(f"OK - pushed {s.status} to Slack")
    return 0


def add_slack_subparser(sub) -> None:
    slack = sub.add_parser("slack", help="Slack integration helpers.")
    slack_sub = slack.add_subparsers(dest="slack_command", required=True)

    setup = slack_sub.add_parser("setup", help="Walk through token creation.")
    setup.set_defaults(handler=cmd_setup)

    test = slack_sub.add_parser("test", help="Verify the saved token.")
    test.set_defaults(handler=cmd_test)

    push = slack_sub.add_parser("push", help="Push the current state to Slack now.")
    push.set_defaults(handler=cmd_push)
