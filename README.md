# luxctl

A small command-line tool for driving a [Luxafor Flag](https://luxafor.com/product/flag/) from Linux, since Luxafor does not ship a native Linux client.

I use it to signal my working state to whoever is walking past the home office. The `stressed` preset triggers the Flag's built-in police siren pattern, which has turned out to be the most honest status of all.

```bash
luxctl status available
luxctl status stressed
luxctl status kid-incoming
luxctl off
```

## Requirements

- A Luxafor Flag (USB, vendor `04d8:f372`)
- Linux with the `hidapi` C library installed
- Python 3.10 or newer

On Ubuntu / Debian:

```bash
sudo apt install libhidapi-hidraw0 libhidapi-libusb0
```

## Install

```bash
git clone https://github.com/madsnorgaard/luxctl
cd luxctl
pip install .
```

Install the udev rule so the Flag is accessible without `sudo`:

```bash
sudo cp udev/99-luxafor.rules /etc/udev/rules.d/
sudo udevadm control --reload-rules
sudo udevadm trigger
```

Replug the device after installing the rule. Your user must be a member of `plugdev` (most desktop Ubuntu installs already are; verify with `id -nG`).

## Usage

List the presets:

```bash
luxctl list
```

Apply a status:

```bash
luxctl status available
luxctl status deep-work
luxctl status stressed
luxctl status on-fire
luxctl status kid-incoming
```

Set an arbitrary colour or turn the light off:

```bash
luxctl rgb 255 0 128
luxctl off
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

Add your own by editing `luxctl/statuses.py`. Each status is a single function decorated with `@register`.

## Current state

Every change persists to `~/.config/luxctl/state.json` so you can ask:

```bash
luxctl current
# => available (via manual at 2026-04-18T15:23:00+00:00)
```

The `--source` flag lets a script identify itself when it changes the light:

```bash
luxctl status meeting --source calendar
luxctl status busy --source slack
```

This is the foundation for the planned external sources (calendar, Slack, Teams). The `Source` interface lives in `luxctl/sources.py`; today only `ManualSource` is implemented, but the resolver already handles priority so a future calendar daemon can override manual settings during a meeting.

## Tray indicator

A GNOME / Ayatana system tray indicator is included. Install the desktop deps:

```bash
sudo apt install python3-gi gir1.2-ayatanaappindicator3-0.1
```

Then run (from a venv created with `--system-site-packages`, or your system Python):

```bash
luxctl tray
```

The menu shows the current state at the top, then groups of presets (Everyday, Developer, Funny, Home office), then Off and Quit. To launch it on login, drop a `.desktop` file into `~/.config/autostart/` pointing at `luxctl tray`.

> On Wayland (Ubuntu's default) the tray icon needs the **AppIndicator and KStatusNotifierItem Support** GNOME extension. Most desktop installs already have it.

## Suggested shortcuts

I bind the common ones to GNOME keyboard shortcuts. For example, `Super+F1` runs `luxctl status available`, `Super+F2` runs `luxctl status busy`, and `Super+F12` runs `luxctl status stressed` on the rare day that warrants it.

A more ambitious integration is to hook this into a Slack or Microsoft Teams presence webhook, or read your Google Calendar to flip `meeting` automatically. That is the next addition — same CLI and tray, driven by a small daemon that registers extra `Source` implementations.

## Development

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[test]"
pytest
```

Tests use a fake HID device and do not require the physical Flag to be plugged in.

## Protocol notes

The Flag accepts 8-byte HID reports. Byte 0 selects the mode, the remaining bytes are mode-specific. The full reference is published by Luxafor at <https://luxafor.com/hid-flag-api/>. The `luxctl/device.py` module documents the modes and constants used.

## Licence

GPL-3.0-or-later. See [LICENSE](LICENSE).
