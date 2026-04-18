"""GNOME / Ayatana system tray indicator.

Optional. Requires the system-level packages:

    sudo apt install python3-gi gir1.2-ayatanaappindicator3-0.1

The tray menu shows the current state at the top, then groups of status
presets, then Off / Quit. Clicking a preset applies it and updates the
header.
"""

from __future__ import annotations

import gi

gi.require_version("Gtk", "3.0")

# Prefer the maintained Ayatana fork; fall back to legacy AppIndicator3.
try:
    gi.require_version("AyatanaAppIndicator3", "0.1")
    from gi.repository import AyatanaAppIndicator3 as AppIndicator3
except (ValueError, ImportError):
    gi.require_version("AppIndicator3", "0.1")
    from gi.repository import AppIndicator3  # type: ignore[no-redef]

from gi.repository import GLib, Gtk

from . import state as state_module
from .device import LuxaforError, LuxaforFlag
from .state import State
from .statuses import STATUSES

PRESET_GROUPS: list[tuple[str, list[str]]] = [
    ("Everyday", ["available", "busy", "meeting", "brb", "offline"]),
    ("Developer", ["deep-work", "pairing", "rubber-duck", "deploying"]),
    ("Funny", ["stressed", "on-fire", "coffee", "lunch"]),
    ("Home office", ["kid-incoming", "party", "dnd"]),
]


def _apply(name: str) -> tuple[bool, str]:
    """Apply a preset and persist state. Returns (ok, message)."""
    try:
        with LuxaforFlag() as light:
            STATUSES[name](light)
        state_module.save(State(
            source="tray",
            set_at=state_module.now_iso(),
            status=name,
        ))
        return True, name
    except LuxaforError as exc:
        return False, str(exc)


def _apply_off() -> tuple[bool, str]:
    try:
        with LuxaforFlag() as light:
            light.off()
        state_module.save(State(
            source="tray",
            set_at=state_module.now_iso(),
            status="offline",
        ))
        return True, "offline"
    except LuxaforError as exc:
        return False, str(exc)


def _header_label() -> str:
    s = state_module.load()
    if s is None:
        return "Currently: (unknown)"
    if s.status:
        return f"Currently: {s.status} (via {s.source})"
    if s.rgb:
        return f"Currently: rgb{s.rgb} (via {s.source})"
    return "Currently: (unknown)"


def run_tray() -> None:
    indicator = AppIndicator3.Indicator.new(
        "luxctl",
        # A widely-available stock icon. Fine for an MVP; can be swapped
        # for a custom SVG later via set_icon_full.
        "preferences-color",
        AppIndicator3.IndicatorCategory.APPLICATION_STATUS,
    )
    indicator.set_status(AppIndicator3.IndicatorStatus.ACTIVE)
    indicator.set_title("luxctl")

    menu = Gtk.Menu()

    header = Gtk.MenuItem(label=_header_label())
    header.set_sensitive(False)
    menu.append(header)
    menu.append(Gtk.SeparatorMenuItem())

    def refresh_header() -> None:
        header.set_label(_header_label())

    def on_select(name: str) -> None:
        ok, msg = _apply(name)
        if not ok:
            _flash_error(indicator, msg)
        refresh_header()

    def on_off() -> None:
        ok, msg = _apply_off()
        if not ok:
            _flash_error(indicator, msg)
        refresh_header()

    for group_label, names in PRESET_GROUPS:
        section = Gtk.MenuItem(label=group_label)
        section.set_sensitive(False)
        menu.append(section)
        for name in names:
            if name not in STATUSES:
                continue
            item = Gtk.MenuItem(label=f"  {name}")
            item.connect("activate", lambda _w, n=name: on_select(n))
            menu.append(item)
        menu.append(Gtk.SeparatorMenuItem())

    off_item = Gtk.MenuItem(label="Turn off")
    off_item.connect("activate", lambda _w: on_off())
    menu.append(off_item)

    refresh_item = Gtk.MenuItem(label="Refresh")
    refresh_item.connect("activate", lambda _w: refresh_header())
    menu.append(refresh_item)

    menu.append(Gtk.SeparatorMenuItem())
    quit_item = Gtk.MenuItem(label="Quit")
    quit_item.connect("activate", lambda _w: Gtk.main_quit())
    menu.append(quit_item)

    menu.show_all()
    indicator.set_menu(menu)

    # Re-read state every 30s so external sources (future calendar daemon)
    # show through in the header without needing a manual refresh.
    GLib.timeout_add_seconds(30, lambda: (refresh_header(), True)[1])

    Gtk.main()


def _flash_error(indicator, message: str) -> None:
    indicator.set_label(" error", "luxctl-error")
    GLib.timeout_add_seconds(5, lambda: (indicator.set_label("", ""), False)[1])
    print(f"luxctl tray: {message}")
