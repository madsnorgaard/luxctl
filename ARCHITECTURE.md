# Architecture

luxctl is small enough that you can read all of it in an afternoon. This doc exists to make that afternoon faster.

## The core idea

Personal presence has multiple, sometimes-conflicting signals (calendar says meeting; OS says screen locked; Slack says away). luxctl treats every signal as a **Source** that produces a `Declaration`, picks the highest-priority one, and pushes the result through every configured **Sink**.

```
                                    +------------------+
   +-----------+   Declaration      |     Daemon       |   ComputedState   +---------+
   |  Source A | ─────────────────→ |  resolve()       | ───────────────→  |  Sink X |
   +-----------+                    |  compose()       |                   +---------+
   +-----------+                    |  apply if change |                   +---------+
   |  Source B | ─────────────────→ |                  | ───────────────→  |  Sink Y |
   +-----------+                    +------------------+                   +---------+
```

This is just the standard data-pipeline pattern (sources/transforms/sinks), specialised to "presence" as the data type.

## Types

`luxctl/types.py`:

```python
@dataclass(frozen=True)
class Declaration:
    status: str        # a preset name from STATUSES
    source: str        # who declared it
    priority: int      # higher wins on collision
    detail: Optional[str] = None   # human context (calendar event title, etc.)

@dataclass(frozen=True)
class ComputedState:
    status: str
    source: str
    active_task: Optional[str] = None
    detail: Optional[str] = None
```

`Declaration` is the source's output; `ComputedState` is what sinks consume. The split lets the daemon enrich the declaration with the persisted active task before fanning it out, so a SlackSink reading `current.display_text()` gets the user's task even though no source declared it.

## Sources

`luxctl/sources/__init__.py`:

```python
class Source(ABC):
    name: str = "unknown"
    priority: int = 0

    @abstractmethod
    def current(self) -> Optional[Declaration]: ...

    def close(self) -> None: ...

def resolve(sources: list[Source]) -> Optional[Declaration]:
    """Pick the highest-priority non-None declaration. Ties: first wins."""
```

Built-in sources:

| File | Class | Notes |
| --- | --- | --- |
| `manual.py` | `ManualSource` | Reads `~/.config/luxctl/state.json`, the file CLI/tray write. Priority 0 (lowest). |
| `idle.py` | `IdleSource` | Mutter idle monitor via `gdbus` (Wayland) or `xprintidle` (X11). |
| `lock.py` | `LockSource` | `loginctl show-session $XDG_SESSION_ID -p LockedHint`. |
| `calendar.py` | `CalendarSource` | `icalendar` + optional `recurring-ical-events`. Caches HTTP fetch for `cache_seconds`. Lazy-imported (optional dep). |
| `slack.py` | `SlackSource` | `slack_sdk.WebClient.users_getPresence`. Polls every `poll_seconds`. Lazy-imported (optional dep). |

### Adding a new source

1. Subclass `Source` in a new file under `luxctl/sources/`.
2. Set `name` and `priority` (slot it between existing ones - see the priority table in the README).
3. Implement `current()` returning `None` when idle, otherwise a `Declaration`.
4. If your source has runtime dependencies, lazy-import them inside `__init__` (so `import luxctl.sources` stays cheap) and add an optional extra in `pyproject.toml`.
5. Register it in `daemon.build_sources()` behind a config flag.

Treat `current()` as cheap and pure - the daemon calls it every tick. Cache anything expensive yourself.

## Sinks

`luxctl/sinks/__init__.py`:

```python
class Sink(ABC):
    name: str = "unknown"

    @abstractmethod
    def apply(self, current: ComputedState) -> None: ...

    def close(self) -> None: ...
```

Built-in sinks:

| File | Class | Notes |
| --- | --- | --- |
| `luxafor.py` | `LuxaforSink` | Looks up `STATUSES[name]` and runs it against the device handle. The Controller passes a shared handle so the daemon never re-opens. |
| `log.py` | `LogSink` | Appends a JSON line per transition to `~/.local/state/luxctl/log.jsonl`. |
| `slack.py` | `SlackSink` | `users.profile.set` + DND. Status text is `current.display_text()`, which prefers `active_task → detail → status`. Lazy-imported. |

### Adding a new sink

Same shape as a source. Implement `apply()` (idempotent - the daemon only calls it on transitions, but treat repeats as safe) and register it in `daemon.build_sinks()`.

`apply()` is allowed to raise. The Controller catches the exception, logs it, and continues with the other sinks.

## Controller

`luxctl/controller.py` owns the device handle and a list of sinks. Used by both the one-shot CLI and the daemon. Its only real job is `apply(current)` - call every sink, isolate failures, persist state.

`apply_status()` is sugar for the CLI: validate the preset name, build the `ComputedState`, apply, persist. The `_KEEP_TASK` sentinel is what makes `luxctl status meeting` preserve a task set earlier with `luxctl task "..."`.

## Daemon

`luxctl/daemon.py` is an asyncio loop:

```python
while not stopping:
    decl = resolve(sources)
    current = compose(decl)        # adds active_task from state.json
    if current != last_applied:
        controller.apply(current)
        last_applied = current
    await wait_or_stop(tick_seconds)
```

The "skip when nothing changed" check makes Slack happy (we are not allowed to spam `users.profile.set`) and keeps the log readable.

Shutdown is signal-driven: `SIGINT`/`SIGTERM` → `daemon.stop()` → loop exits → sources and sinks closed.

## State files

| Path | What | Who writes |
| --- | --- | --- |
| `~/.config/luxctl/state.json` | Last-applied state + active task | CLI, tray, daemon |
| `~/.config/luxctl/config.toml` | User config | You |
| `~/.config/luxctl/secrets.toml` | Slack token (chmod 600 enforced) | `luxctl slack setup` |
| `~/.local/state/luxctl/log.jsonl` | Transition history | LogSink |

Paths follow XDG Base Directory.

## Testing strategy

Every source and sink takes its expensive collaborator as a constructor argument:

- `LuxaforFlag(device=...)` - pass a fake HID device.
- `IdleSource(idle_reader=...)` - pass a function returning ms.
- `SlackSink(client=...)` - pass a `MagicMock`.
- `CalendarSource(path=...)` - point at a fixture .ics.

That keeps the unit tests:
- Hardware-free (CI runs them on plain `ubuntu-latest`).
- Network-free (no Slack, no calendar URLs).
- Deterministic (the daemon's tick is exposed publicly so we can drive it without sleeping).

127 tests, ~0.2 seconds wall-time.

## Design choices, briefly justified

- **TOML over YAML** - stdlib `tomllib`, no extra dep, less footgun.
- **Optional extras over hard deps** - keeps `pip install luxctl` light; the user opts into Slack / calendar / tray.
- **Subprocess `gdbus`/`loginctl` over `dbus-next`** - no python-dbus dep, works on every modern Linux desktop, easy to mock.
- **asyncio over threads** - single-process, no locking, clean signal handling.
- **Source priority as a static int** - could be made dynamic (e.g. "manual wins for the next 30 min"), but YAGNI until I actually want it.
- **Sink failures are logged, not raised** - the daemon stays up if my home wifi blips a Slack call.
