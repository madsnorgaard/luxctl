# luxctl

A Linux command-line tool, GTK tray, and presence-aggregator daemon for the [Luxafor Flag](https://luxafor.com/product/flag/), a USB status light.

luxctl pairs the physical light with a small **presence pipeline**: any number of *sources* (calendar, screen lock, idle detection, Slack presence, custom) declare what status should be shown, the daemon picks the highest-priority declaration, and any number of *sinks* (the Luxafor itself, your Slack profile and DND, a transition log, custom) reflect the resolved state outwards.

```
        Sources                 Daemon                 Sinks
   manual ──┐                                    ┌── Luxafor Flag
   idle ────┤                                    ├── Slack status + DND
   lock ────┼─→  resolve(priority) → ComputedState ──┼── Log (jsonl)
   calendar ┤                                    └── (your sink here)
   slack ───┘
```

Vendor `04d8:f372` (Luxafor Flag). The base CLI also works for many Luxafor variants that share the protocol; unsupported pattern IDs are caught with a clear error.

## Quick start

```bash
git clone https://github.com/madsnorgaard/luxctl
cd luxctl
sudo apt install libhidapi-hidraw0 libhidapi-libusb0
python3 -m venv --system-site-packages .venv
.venv/bin/pip install -e ".[all]"

# udev rule so the device is writable without sudo:
sudo cp udev/99-luxafor.rules /etc/udev/rules.d/
sudo udevadm control --reload-rules
sudo udevadm trigger --action=change --subsystem-match=usb --subsystem-match=hidraw

# interactive setup (config + Slack + autostart):
.venv/bin/luxctl init

# verify everything:
.venv/bin/luxctl doctor
```

If anything is wrong, `luxctl doctor` tells you exactly what to fix.

## Commands

```text
luxctl init                first-run wizard (config + Slack + systemd)
luxctl doctor              audit install and config end-to-end

luxctl status <name>       apply a preset; --task "..." sets active task
luxctl rgb R G B           arbitrary colour
luxctl off                 black
luxctl list                list all presets (built-in + custom)
luxctl current             show last-applied state, source, task
luxctl task "<text>"       set the active task (persists across status changes)
luxctl task --clear

luxctl tray                GNOME indicator
luxctl daemon              presence-aggregator loop (foreground)
luxctl logs -f             tail the transition log
luxctl stats [--week]      time spent per status

luxctl install-service     install + enable + start systemd user service
luxctl uninstall-service   stop, disable, remove
luxctl service-status      is the daemon installed/active/enabled?

luxctl slack setup         walk through Slack token creation
luxctl slack test          verify the saved token
luxctl slack push          push current state to Slack one-shot
```

Tab completion: `pip install '.[completion]'`, then per-shell:

```bash
# bash
eval "$(register-python-argcomplete luxctl)"
# zsh
autoload -U bashcompinit && bashcompinit
eval "$(register-python-argcomplete luxctl)"
# fish
register-python-argcomplete --shell fish luxctl | source
```

## Built-in presets

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

## Custom presets (no Python needed)

Add `[presets.*]` blocks to `~/.config/luxctl/config.toml`:

```toml
[presets.coding]
static = [50, 200, 50]
description = "Solid green-ish, hands on the keyboard."

[presets.urgent]
strobe = [255, 0, 0]
speed = 5
repeat = 30

[presets.afk]
fade = [80, 80, 80]
speed = 60
```

Supported keys per preset: `static`, `fade`, `strobe`, `wave`, `pattern` (1-8). Modifiers: `speed`, `repeat`, `wave_type`. Re-using a built-in name overrides it.

## Active task

The active task is free-form text that travels alongside the status. The Luxafor itself can't display text, but the tray menu shows it and the **Slack sink uses it as your Slack `status_text`**:

```bash
luxctl task "Reviewing PR #1234"
luxctl status busy            # task survives the status change
```

Slack profile becomes `🚫 Reviewing PR #1234`. `luxctl task --clear` removes it.

## Configuration

`~/.config/luxctl/config.toml` (annotated copy at `docs/example-config.toml`):

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

Secrets live separately at `~/.config/luxctl/secrets.toml` (the loader refuses anything not `chmod 600`):

```toml
[slack]
token = "xoxp-..."
```

`luxctl slack setup` writes this for you.

## Source priority

Higher priority wins when several sources declare at once.

| Source | Priority | Declares |
| --- | --- | --- |
| `manual` | 0 | Whatever you set via CLI/tray |
| `idle` | 10 | `brb` after N min input idleness, `offline` after M min |
| `calendar` | 20 | `meeting` while a calendar event is active |
| `lock` | 30 | `offline` while the screen is locked |
| `slack` | 40 | `brb` when Slack reports your presence as `away` |

A locked screen always wins. Setting `busy` manually during a calendar event will be overridden the next tick. Override semantics ("manual wins for the next 30 min") are on the roadmap.

## Tray indicator

```bash
luxctl tray
```

Menu: current state, active task, "Set task..." dialog, four preset groups, Refresh, Quit. To autostart on login, drop a `.desktop` file in `~/.config/autostart/` pointing at `luxctl tray`.

On Wayland the tray needs the **AppIndicator and KStatusNotifierItem Support** GNOME extension; standard on Ubuntu desktops, install with `sudo apt install gnome-shell-extension-appindicator` on stripped-down setups.

## Daemon and autostart

```bash
luxctl install-service     # writes ~/.config/systemd/user/luxctl.service, enables, starts
journalctl --user -fu luxctl.service
```

The unit auto-detects which `luxctl` binary you're running (venv or `~/.local/bin`) and bakes that into `ExecStart`. If you move the install, re-run `luxctl install-service`.

## Architecture

[ARCHITECTURE.md](ARCHITECTURE.md) covers the source/sink contract, how to add your own, and the daemon's resolution loop.

## Contributing

[CONTRIBUTING.md](CONTRIBUTING.md). Adding a new source or sink is roughly 30 lines plus tests.

## Development

```bash
python3 -m venv --system-site-packages .venv
source .venv/bin/activate
pip install -e ".[test,calendar,slack]"
pytest                         # ~150 tests, no hardware or network required
```

Tests use a fake HID device and mocked Slack/iCal; they pass on a clean CI runner with no Luxafor and no internet.

## Protocol notes

The Flag accepts 8-byte HID command payloads, prefixed by a 1-byte report ID on the wire (9 bytes total via hidraw). Byte 0 selects the mode, the rest are mode-specific. Full reference at <https://luxafor.com/hid-flag-api/>; constants are in `luxctl/device.py`.

## Licence

GPL-3.0-or-later. See [LICENSE](LICENSE).
