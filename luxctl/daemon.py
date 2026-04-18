"""The presence-aggregator daemon.

Reads ~/.config/luxctl/config.toml + secrets.toml, instantiates the
configured sources and sinks, and runs an asyncio loop that:

  1. polls every source for a Declaration
  2. resolves to the highest-priority one
  3. composes a ComputedState (with active_task pulled from local state)
  4. on change, applies it to every sink (failures isolated)

Falls back to a minimal default config if neither file exists: just the
manual source + the Luxafor + log sinks. So `luxctl daemon` works out of
the box even before any TOML editing.
"""

from __future__ import annotations

import asyncio
import logging
import os
import signal
from typing import Optional

from . import config as config_module
from . import state as state_module
from .config import Config
from .controller import Controller
from .sinks import LogSink, LuxaforSink, Sink
from .sources import IdleSource, LockSource, ManualSource, Source, resolve
from .types import ComputedState

log = logging.getLogger("luxctl.daemon")


def build_sources(cfg: Config, secrets: dict) -> list[Source]:
    sources: list[Source] = [ManualSource()]

    if cfg.idle.enabled:
        sources.append(IdleSource(
            away_minutes=cfg.idle.away_minutes,
            offline_minutes=cfg.idle.offline_minutes,
        ))
    if cfg.lock.enabled:
        sources.append(LockSource())

    if cfg.calendar.enabled and cfg.calendar.url:
        try:
            from .sources import CalendarSource  # type: ignore[attr-defined]
            sources.append(CalendarSource(
                url=cfg.calendar.url,
                cache_seconds=cfg.calendar.cache_seconds,
            ))
        except ImportError as exc:
            log.warning("calendar source disabled: %s", exc)

    if cfg.slack.enabled:
        slack_token = secrets.get("slack", {}).get("token")
        if slack_token:
            try:
                from .sources import SlackSource  # type: ignore[attr-defined]
                sources.append(SlackSource(
                    token=slack_token,
                    poll_seconds=cfg.slack.poll_seconds,
                ))
            except ImportError as exc:
                log.warning("slack source disabled: %s", exc)
        else:
            log.warning("slack source enabled but no token in secrets.toml")

    return sources


def build_sinks(cfg: Config, secrets: dict) -> list[Sink]:
    sinks: list[Sink] = [LuxaforSink(), LogSink()]

    if cfg.slack.enabled:
        slack_token = secrets.get("slack", {}).get("token")
        if slack_token:
            try:
                from .sinks import SlackSink  # type: ignore[attr-defined]
                sinks.append(SlackSink(
                    token=slack_token,
                    emoji_map=cfg.slack.emoji_map,
                    set_dnd_for=cfg.slack.set_dnd_for,
                ))
            except ImportError as exc:
                log.warning("slack sink disabled: %s", exc)

    return sinks


def compose(decl, fallback_status: str = "available") -> ComputedState:
    """Convert a Declaration + the persisted active_task into a ComputedState."""
    s = state_module.load()
    active_task = s.active_task if s else None
    if decl is None:
        # Nothing declared — keep the light at the fallback (or whatever
        # was last manually set if it's still present in state).
        return ComputedState(
            status=fallback_status,
            source="default",
            active_task=active_task,
        )
    return ComputedState(
        status=decl.status,
        source=decl.source,
        active_task=active_task,
        detail=decl.detail,
    )


class Daemon:
    def __init__(
        self,
        sources: list[Source],
        controller: Controller,
        tick_seconds: float = 5.0,
        fallback_status: str = "available",
    ) -> None:
        self.sources = sources
        self.controller = controller
        self.tick_seconds = tick_seconds
        self.fallback_status = fallback_status
        self._last_applied: Optional[ComputedState] = None
        self._stopping = asyncio.Event()

    def stop(self) -> None:
        self._stopping.set()

    def tick(self) -> Optional[ComputedState]:
        """Run one resolution + apply cycle. Returns the applied state, or
        None if nothing changed. Public for testing."""
        decl = resolve(self.sources)
        current = compose(decl, fallback_status=self.fallback_status)
        if current == self._last_applied:
            return None
        results = self.controller.apply(current)
        for name, err in results:
            if err:
                log.warning("sink %s failed: %s", name, err)
        log.info("→ %s (via %s)", current.status, current.source)
        self._last_applied = current
        return current

    async def run(self) -> None:
        log.info(
            "daemon up: %d source(s), %d sink(s), tick=%ss",
            len(self.sources),
            len(self.controller.sinks),
            self.tick_seconds,
        )
        try:
            while not self._stopping.is_set():
                try:
                    self.tick()
                except Exception as exc:  # noqa: BLE001
                    log.exception("tick failed: %s", exc)
                try:
                    await asyncio.wait_for(
                        self._stopping.wait(), timeout=self.tick_seconds
                    )
                except asyncio.TimeoutError:
                    pass
        finally:
            for src in self.sources:
                try:
                    src.close()
                except Exception:  # noqa: BLE001
                    pass
            self.controller.close()
            log.info("daemon stopped")


def run_daemon() -> None:
    logging.basicConfig(
        level=os.environ.get("LUXCTL_LOG", "INFO").upper(),
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )

    cfg = config_module.parse(config_module.load_config())
    try:
        secrets = config_module.load_secrets()
    except config_module.ConfigError as exc:
        log.error("%s", exc)
        raise SystemExit(1) from exc

    sources = build_sources(cfg, secrets)
    sinks = build_sinks(cfg, secrets)
    controller = Controller(sinks=sinks)
    daemon = Daemon(
        sources=sources,
        controller=controller,
        tick_seconds=cfg.daemon.tick_seconds,
    )

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, daemon.stop)

    try:
        loop.run_until_complete(daemon.run())
    finally:
        loop.close()
