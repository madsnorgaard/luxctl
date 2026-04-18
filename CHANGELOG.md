# Changelog

All notable changes to luxctl. Format loosely follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

## [0.2.0] — 2026-04-18

The "presence aggregator" release. luxctl is no longer just a fancy CLI for
the Luxafor; it now resolves presence from multiple sources and reflects the
result through multiple sinks (Luxafor, Slack, log).

### Added

- **Source / Sink architecture** (`luxctl/sources/`, `luxctl/sinks/`).
  - `Source` ABC + `resolve(sources)` priority resolver.
  - `Sink` ABC; sink failures are isolated by the Controller.
- **Local sources** (no API keys):
  - `IdleSource` — Mutter idle monitor (Wayland) / xprintidle (X11).
  - `LockSource` — logind `LockedHint`.
  - `CalendarSource` — iCal feed via `icalendar`, optional RRULE expansion.
- **Slack integration** (`pip install '.[slack]'`):
  - `SlackSink` — sets `users.profile.set` (text + emoji) and DND.
  - `SlackSource` — polls `users.getPresence`.
  - `luxctl slack setup` walks token creation; `slack test` verifies; `slack push` fires the current state.
- **Daemon** (`luxctl daemon`) — asyncio loop with signal-driven shutdown.
- **systemd user unit** (`systemd/luxctl.service`).
- **Active task** field — free-form text that flows into Slack `status_text`. `luxctl task "..."`, `luxctl task --clear`.
- **Config + secrets** (`~/.config/luxctl/config.toml`, `secrets.toml`). Secrets must be `chmod 600`.
- **`luxctl current`** to print the persisted state.
- **`luxctl logs -f`** to tail transitions.
- `Controller` orchestrating device handle ownership + sink fan-out.
- ARCHITECTURE.md and `docs/example-config.toml`.
- `[calendar]`, `[slack]`, `[all]` optional extras.

### Changed

- `luxctl status` now records the `--source` you specify (default: `cli`); the manual source treats `cli`, `tray`, and `manual` interchangeably.
- Tray menu groups presets (Everyday / Developer / Funny / Home office), shows the active task, and exposes a "Set task…" modal.
- HID write now prepends a report-ID byte (required by hidraw on Linux). The on-the-wire packet is 9 bytes (1 report ID + 8 payload). No user-visible change.

### Fixed

- `LuxaforFlag.__init__` previously called the legacy `hid.device()` API; now uses `hid.Device(vid, pid)` from the modern `hid` package.

## [0.1.0] — 2026-04-18

Initial release.

- HID protocol wrapper for the Luxafor Flag (`04d8:f372`).
- 16 status presets (`available`, `busy`, `meeting`, `stressed/police siren`, …).
- CLI: `status`, `rgb`, `off`, `list`.
- udev rule for non-root device access.
- GitHub Actions CI on Python 3.10–3.13.
- 61 unit tests.
