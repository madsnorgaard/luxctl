# luxctl

A Linux command-line tool, GTK tray, and presence-aggregator daemon for the [Luxafor Flag](https://luxafor.com/product/flag/).

Started as a personal "make the desk light show police siren when I am stressed" project, then grew into a small presence hub: multiple sources (calendar, screen lock, idle detection, Slack) declare what status I should be at, and the daemon reflects the resolved state outwards (Luxafor light, Slack profile + DND, transition log).

```
        Sources                 Daemon                 Sinks
   manual ──┐                                    ┌── Luxafor Flag
   idle ────┤                                    ├── Slack status + DND
   lock ────┼─→  resolve(priority) → ComputedState ──┼── Log (jsonl)
   calendar ┤                                    └── (your sink here)
   slack ───┘
```

## Quick start

```bash
git clone https://github.com/madsnorgaard/luxctl
cd luxctl
sudo apt install libhidapi-hidraw0 libhidapi-libusb0
pip install ".[all]"

# udev rule so you don't need sudo for every command:
sudo cp udev/99-luxafor.rules /etc/udev/rules.d/
sudo udevadm control --reload-rules
sudo udevadm trigger --action=change --subsystem-match=usb --subsystem-match=hidraw

# try it
luxctl status available
luxctl status stressed     # police siren
luxctl status kid-incoming # pink pulse
luxctl off
```

## Requirements

- A Luxafor Flag (USB, vendor `04d8:f372`)
- Linux with `hidapi` C library (`sudo apt install libhidapi-hidraw0 libhidapi-libusb0`)
- Python 3.10 or newer

For the **tray**: `sudo apt install python3-gi gir1.2-ayatanaappindicator3-0.1` and create the venv with `python3 -m venv --system-site-packages .venv` so it can see PyGObject.

For the **daemon's optional sources**: `pip install ".[calendar]"` for iCal feeds, `pip install ".[slack]"` for Slack. Or just `pip install ".[all]"`.

## CLI

```text
luxctl status <name>       # apply a preset; --task "..." sets active task
luxctl rgb R G B           # arbitrary colour
luxctl off                 # back to black
luxctl list                # list all presets
luxctl current             # show last-applied state, source, task
luxctl task "<text>"       # set the active task (persists across status changes)
luxctl task --clear
luxctl tray                # GNOME indicator
luxctl daemon              # presence-aggregator loop
luxctl logs -f             # tail the transition log
luxctl slack setup         # walk through token creation
luxctl slack test          # verify the saved token
luxctl slack push          # push current state to Slack one-shot
```

## Presets

| Name | Behaviour |
| --- | --- |
| `available` | Solid green |
| `busy` | Solid red |
| `meeting` | Solid blue |
| `brb` | Yellow fade |
| `deep-work` | Slow purple fade |
| `pairing` | Solid cyan |
| `rubber-duck` | Yellow fade (debugging) |
| `deploying` | Built-in rainbow pattern |
| `stressed` | Built-in police siren pattern |
| `on-fire` | Rapid red strobe |
| `coffee` | Orange fade |
| `lunch` | Yellow slow strobe |
| `kid-incoming` | Pink pulse |
| `party` | Rainbow, fast |
| `dnd` | Red strobe |
| `offline` | Off |

Add your own by editing `luxctl/statuses.py` — each status is a single function decorated with `@register`.

## Active task

The active task is free-form text that travels with whatever status is set. The Luxafor doesn't display text, but the tray menu shows it and the **SlackSink uses it as your Slack `status_text`**, so:

```bash
luxctl task "Reviewing PR #1234"
luxctl status busy           # task survives the status change
```

…appears in Slack as `🚫 Reviewing PR #1234`. `luxctl task --clear` removes it.

## Tray indicator

```bash
luxctl tray
```

Menu shows the current state and active task at the top, then groups of presets (Everyday, Developer, Funny, Home office), then a "Set task…" entry, "Refresh", "Quit".

To autostart it on login: drop a `.desktop` file in `~/.config/autostart/` pointing at `luxctl tray`. On Wayland (Ubuntu's default) you need the **AppIndicator and KStatusNotifierItem Support** GNOME extension; most desktop installs already ship it.

## Daemon

```bash
luxctl daemon
```

Polls the configured sources every `tick_seconds` (default 5), resolves the highest-priority declaration, and pushes the resulting `ComputedState` to every configured sink. Source exceptions are caught and logged; sink failures are isolated so one broken sink does not stop the others.

For autostart, install the systemd user unit:

```bash
mkdir -p ~/.config/systemd/user
cp systemd/luxctl.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now luxctl.service
journalctl --user -fu luxctl.service    # watch the live log
```

## Configuration

`~/.config/luxctl/config.toml` (see `docs/example-config.toml` for a complete annotated copy):

```toml
[daemon]
tick_seconds = 5

[idle]
enabled = true
away_minutes = 5
offline_minutes = 30

[lock]
enabled = true

[calendar]
enabled = true
url = "https://calendar.google.com/calendar/ical/.../basic.ics"
cache_seconds = 60

[slack]
enabled = true
poll_seconds = 30
set_dnd_for = ["stressed", "dnd", "on-fire"]

[slack.emoji_map]
busy = ":lock:"
meeting = ":calendar:"
```

Secrets live separately at `~/.config/luxctl/secrets.toml` (the loader refuses anything that isn't `chmod 600`):

```toml
[slack]
token = "xoxp-..."
```

`luxctl slack setup` walks you through creating an internal Slack app and writes this file for you.

## Source priority

Higher priority wins on ties.

| Source | Default priority | Declares |
| --- | --- | --- |
| `manual` | 0 | Whatever you set via CLI/tray |
| `idle` | 10 | `brb` after 5 min of input idleness, `offline` after 30 min |
| `calendar` | 20 | `meeting` while a calendar event is active |
| `lock` | 30 | `offline` while the screen is locked |
| `slack` | 40 | `brb` when Slack reports your presence as `away` |

So: lock > slack-away > calendar-meeting > idle-away > whatever you set manually. A locked screen always wins; setting `busy` manually during a calendar event will be overridden the next tick. (The intentional override flow is on the roadmap.)

## Architecture

See [ARCHITECTURE.md](ARCHITECTURE.md) for the source/sink contract, how to add your own source or sink, and the daemon's resolution loop.

## Development

```bash
python -m venv --system-site-packages .venv  # so `import gi` works for tray tests
source .venv/bin/activate
pip install -e ".[test,calendar,slack]"
pytest                  # 127 tests, no hardware or network required
```

Tests use a fake HID device and mocked Slack/iCal — they pass on a CI runner with no Luxafor and no network access.

## Protocol notes

The Flag accepts 8-byte HID command payloads, prefixed by a 1-byte report ID on the wire (so 9 bytes total via hidraw). Byte 0 selects the mode, the rest are mode-specific. Full reference at <https://luxafor.com/hid-flag-api/>; constants are in `luxctl/device.py`.

## Licence

GPL-3.0-or-later. See [LICENSE](LICENSE).
