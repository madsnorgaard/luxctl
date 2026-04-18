"""'luxctl init': interactive first-run setup.

Steps the user through:
  1. Copy the example config to ~/.config/luxctl/config.toml (if missing).
  2. Optionally adjust idle thresholds.
  3. Optionally paste a calendar iCal URL.
  4. Optionally run the Slack token wizard.
  5. Optionally install the systemd user service and start it.

Each step is skippable. The default for every prompt is the safe choice
(skip / keep current).
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

from . import config as config_module
from . import service as service_module


def _ask(prompt: str, default: str = "n") -> str:
    suffix = " [Y/n] " if default == "y" else " [y/N] "
    try:
        ans = input(prompt + suffix).strip().lower()
    except (EOFError, KeyboardInterrupt):
        print()
        return ""
    return ans or default


def _ask_text(prompt: str, default: str = "") -> str:
    text = f"{prompt} "
    if default:
        text += f"[{default}] "
    try:
        ans = input(text).strip()
    except (EOFError, KeyboardInterrupt):
        print()
        return ""
    return ans or default


def _seed_config() -> Path | None:
    target = config_module.config_path()
    if target.exists():
        print(f"  config already at {target} (skipping)")
        return target
    here = Path(__file__).parent.parent
    example = here / "docs" / "example-config.toml"
    if not example.exists():
        print(f"  could not find {example}; skipping seed")
        return None
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(example, target)
    print(f"  wrote {target}")
    return target


def _patch_calendar(config_path: Path, url: str) -> None:
    """Minimal in-place edit. Keeps comments intact."""
    text = config_path.read_text()
    text = text.replace(
        "REPLACE_ME/basic.ics",
        url.split("calendar/ical/", 1)[-1] if "calendar/ical/" in url else url,
    )
    if 'url = "https://' not in text and url.startswith("https://"):
        text += f'\n[calendar]\nenabled = true\nurl = "{url}"\n'
    else:
        text = text.replace(
            '[calendar]\n# Declares "meeting" during any active iCal event.\n# Get the URL from Google Calendar',
            '[calendar]\n# (set up by luxctl init)\n# Get the URL from Google Calendar',
        )
        text = text.replace(
            "enabled = false\nurl = \"https://calendar.google.com/calendar/ical/REPLACE_ME/basic.ics\"",
            f"enabled = true\nurl = \"{url}\"",
        )
    config_path.write_text(text)


def _enable_slack(config_path: Path) -> None:
    text = config_path.read_text()
    text = text.replace(
        "[slack]\n# Reads your Slack presence (active/away) AND writes your Slack profile\n"
        "# (status text + emoji + DND). Token lives in secrets.toml - run:\n"
        "#   luxctl slack setup\nenabled = false",
        "[slack]\nenabled = true",
    )
    config_path.write_text(text)


def run() -> int:
    print("luxctl init")
    print("===========")
    print("This will set up a fresh config. Each step is optional.\n")

    print("Step 1: seed ~/.config/luxctl/config.toml from the example")
    config_path = _seed_config()
    if config_path is None:
        return 1
    print()

    print("Step 2: idle thresholds")
    if _ask("Adjust idle thresholds now?", default="n").startswith("y"):
        away = _ask_text("Minutes of input idleness before 'brb':", default="5")
        offline = _ask_text("Minutes of input idleness before 'offline':", default="30")
        text = config_path.read_text()
        text = text.replace("away_minutes = 5", f"away_minutes = {away}")
        text = text.replace("offline_minutes = 30", f"offline_minutes = {offline}")
        config_path.write_text(text)
        print(f"  set away={away}m, offline={offline}m")
    else:
        print("  skipped (defaults: 5m / 30m)")
    print()

    print("Step 3: calendar")
    if _ask("Wire up an iCal feed (Google Calendar / Outlook / etc)?", default="n").startswith("y"):
        url = _ask_text("Paste the iCal URL:")
        if url.startswith("http"):
            _patch_calendar(config_path, url)
            print("  calendar enabled")
        else:
            print("  no URL provided, skipped")
    else:
        print("  skipped")
    print()

    print("Step 4: Slack")
    if _ask("Set up Slack now? (creates a Slack app, takes ~2 minutes)", default="n").startswith("y"):
        from .slack_cli import cmd_setup
        rc = cmd_setup(None)
        if rc == 0:
            _enable_slack(config_path)
            print("  slack enabled in config.toml")
        else:
            print("  slack setup did not complete; you can re-run 'luxctl slack setup' later")
    else:
        print("  skipped")
    print()

    print("Step 5: systemd autostart")
    if _ask("Install the systemd user service so the daemon starts at login?", default="y").startswith("y"):
        service_module.install()
    else:
        print("  skipped (run 'luxctl install-service' anytime)")
    print()

    print("Done. Next steps:")
    print("  luxctl doctor      verify the install")
    print("  luxctl status busy try a status")
    print("  luxctl tray        launch the GNOME indicator")
    return 0
