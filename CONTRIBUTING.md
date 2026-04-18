# Contributing to luxctl

Thanks for considering it. The codebase is small (about 2k lines) and the core abstractions, `Source` and `Sink`, are designed for outsiders to plug into.

## Quick orientation

```
luxctl/
  device.py        HID protocol wrapper. Pure transport, no policy.
  statuses.py      Built-in status presets + the registry.
  state.py         Persisted last-applied state + active task.
  types.py         Declaration, ComputedState dataclasses.
  sources/         Pluggable inputs.
  sinks/           Pluggable outputs.
  controller.py    Owns the device handle, fans state to sinks.
  daemon.py        Asyncio loop tying it all together.
  cli.py           Argparse entry point.
  tray.py          GNOME indicator (optional).
  config.py        TOML config + secrets.
  doctor.py        Self-diagnostic.
  service.py       systemd user unit install/uninstall.
  init_cli.py      First-run wizard.
  stats.py         Time-spent reporter.
  diagnostics.py   Shared device checks.
```

[ARCHITECTURE.md](ARCHITECTURE.md) explains the data flow.

## Local setup

```bash
git clone https://github.com/madsnorgaard/luxctl
cd luxctl
sudo apt install libhidapi-hidraw0 libhidapi-libusb0 \
                 python3-gi gir1.2-ayatanaappindicator3-0.1
python3 -m venv --system-site-packages .venv
source .venv/bin/activate
pip install -e ".[test,calendar,slack,completion]"
pytest
```

No hardware is needed for the test suite; the device is faked.

## Adding a new source

A source declares "I think the light should be at status X". Example: a `WebhookSource` that reads `~/.cache/luxctl/external-status` (written by some external script via `curl`).

1. Create `luxctl/sources/webhook.py`:

   ```python
   from pathlib import Path
   from typing import Optional
   from ..types import Declaration
   from . import Source

   class WebhookSource(Source):
       name = "webhook"
       priority = 25  # between calendar (20) and lock (30)

       def __init__(self, path: Path):
           self.path = path

       def current(self) -> Optional[Declaration]:
           if not self.path.exists():
               return None
           text = self.path.read_text().strip()
           if not text:
               return None
           return Declaration(
               status=text, source=self.name, priority=self.priority,
           )
   ```

2. If your source has runtime dependencies, lazy-import them inside the source file and add an optional extra in `pyproject.toml`. Keep `import luxctl.sources` cheap.

3. Register it from the daemon. In `luxctl/daemon.py:build_sources()`:

   ```python
   if cfg.webhook.enabled:
       from .sources.webhook import WebhookSource
       sources.append(WebhookSource(path=Path(cfg.webhook.path)))
   ```

4. Add a config dataclass in `luxctl/config.py` so `cfg.webhook.enabled` works, and parse it in `parse()`.

5. Test it. Pass any expensive collaborator as a constructor argument:

   ```python
   def test_webhook_source_reads_file(tmp_path):
       p = tmp_path / "status"
       p.write_text("busy")
       decl = WebhookSource(path=p).current()
       assert decl.status == "busy"
   ```

That's it. The daemon will start polling your source on its next tick.

## Adding a new sink

Same shape as a source. A sink reflects the resolved `ComputedState` outwards. Example: a `NotifySink` that pops a desktop notification on every transition.

```python
import subprocess
from ..types import ComputedState
from . import Sink

class NotifySink(Sink):
    name = "notify"

    def apply(self, current: ComputedState) -> None:
        subprocess.run([
            "notify-send", "luxctl", f"now: {current.display_text()}",
        ], check=False)
```

Register it in `daemon.build_sinks()`. Sinks are allowed to raise; the Controller catches the exception, logs it, and continues with the others.

## Adding a custom preset

If you only want a new colour or pattern, you don't need code at all. See the *Custom presets* section in the README. Add `[presets.my-status]` to `~/.config/luxctl/config.toml`.

If you want a built-in shipped to all users, add a function to `luxctl/statuses.py`:

```python
@register("focus", "Solid teal. Hands on the keyboard.")
def focus(light: LuxaforFlag) -> None:
    light.static(0, 180, 180)
```

## Tests

- `pytest -q` should pass on a fresh clone.
- New code without tests is unlikely to be merged.
- Mock external collaborators (HID device, Slack client, gdbus subprocess). The existing `tests/conftest.py` provides a fake HID; copy that pattern.
- Do not hit the network from tests.

## Style

- Use `from __future__ import annotations` so type hints stay string-form.
- No em dashes anywhere (use a hyphen, comma, or colon).
- Keep docstrings short and aimed at a future maintainer.
- `ruff check` and `ruff format` are not enforced yet but will not be turned away.

## Bug reports

Include the output of `luxctl doctor` and `luxctl --version`. If a daemon issue, also `journalctl --user -u luxctl.service --since "10 minutes ago"`.

## Pull request checklist

- [ ] `pytest` passes.
- [ ] CHANGELOG.md updated under `[Unreleased]`.
- [ ] If adding a source or sink: registered in the daemon, documented in README, tests included.
- [ ] If adding an optional dependency: declared in `pyproject.toml` as an extra, lazy-imported in the using module.
- [ ] `luxctl doctor` still reports no false-positive failures on your setup.
