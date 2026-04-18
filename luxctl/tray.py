"""GNOME / Ayatana system tray indicator.

Optional. Requires:

    sudo apt install python3-gi gir1.2-ayatanaappindicator3-0.1

The tray menu shows the current state and active task at the top, then
groups of status presets, then Off / Quit. Clicking a preset applies it
through the Controller (so all configured sinks fire - Luxafor, log,
Slack if enabled).
"""

from __future__ import annotations

import gi

gi.require_version("Gtk", "3.0")
try:
    gi.require_version("AyatanaAppIndicator3", "0.1")
    from gi.repository import AyatanaAppIndicator3 as AppIndicator3
except (ValueError, ImportError):
    gi.require_version("AppIndicator3", "0.1")
    from gi.repository import AppIndicator3  # type: ignore[no-redef]

from gi.repository import GLib, Gtk

from . import state as state_module
from .controller import Controller
from .device import LuxaforError
from .statuses import STATUSES

PRESET_GROUPS: list[tuple[str, list[str]]] = [
    ("Everyday", ["available", "busy", "meeting", "brb", "offline"]),
    ("Developer", ["deep-work", "pairing", "rubber-duck", "deploying"]),
    ("Funny", ["stressed", "on-fire", "coffee", "lunch"]),
    ("Home office", ["kid-incoming", "party", "dnd"]),
]


def _apply(name: str) -> tuple[bool, str]:
    try:
        with Controller() as ctrl:
            ctrl.apply_status(name, source="tray")
        return True, name
    except LuxaforError as exc:
        return False, str(exc)


def _header_label() -> str:
    s = state_module.load()
    if s is None:
        return "Currently: (unknown)"
    if s.status:
        return f"● {s.status}  (via {s.source})"
    if s.rgb:
        return f"● rgb{s.rgb}  (via {s.source})"
    return "● (unknown)"


def _task_label() -> str:
    s = state_module.load()
    if s and s.active_task:
        return f"Task: {s.active_task}"
    return "Task: (none)"


def _prompt_task(parent_window=None) -> str | None:
    """Modal text-entry dialog for setting the active task."""
    dialog = Gtk.Dialog(
        title="Set active task",
        transient_for=parent_window,
        flags=0,
    )
    dialog.add_buttons(
        "Clear", Gtk.ResponseType.REJECT,
        Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
        Gtk.STOCK_OK, Gtk.ResponseType.OK,
    )
    dialog.set_default_size(380, 80)
    box = dialog.get_content_area()
    entry = Gtk.Entry()
    entry.set_placeholder_text("e.g. Reviewing PR #123")
    s = state_module.load()
    if s and s.active_task:
        entry.set_text(s.active_task)
    entry.set_activates_default(True)
    box.add(entry)
    dialog.set_default_response(Gtk.ResponseType.OK)
    box.show_all()
    response = dialog.run()
    text = entry.get_text().strip()
    dialog.destroy()
    if response == Gtk.ResponseType.OK:
        return text or ""
    if response == Gtk.ResponseType.REJECT:
        return ""  # explicit clear
    return None  # cancel


def run_tray() -> None:
    indicator = AppIndicator3.Indicator.new(
        "luxctl",
        "preferences-color",
        AppIndicator3.IndicatorCategory.APPLICATION_STATUS,
    )
    indicator.set_status(AppIndicator3.IndicatorStatus.ACTIVE)
    indicator.set_title("luxctl")

    menu = Gtk.Menu()

    header = Gtk.MenuItem(label=_header_label())
    header.set_sensitive(False)
    menu.append(header)

    task_label = Gtk.MenuItem(label=_task_label())
    task_label.set_sensitive(False)
    menu.append(task_label)

    set_task_item = Gtk.MenuItem(label="Set task…")
    menu.append(set_task_item)
    menu.append(Gtk.SeparatorMenuItem())

    def refresh() -> None:
        header.set_label(_header_label())
        task_label.set_label(_task_label())

    def on_select(name: str) -> None:
        ok, msg = _apply(name)
        if not ok:
            print(f"luxctl tray: {msg}")
        refresh()

    def on_set_task(_w) -> None:
        text = _prompt_task()
        if text is None:
            return
        if text == "":
            state_module.update(active_task=None)
        else:
            state_module.update(active_task=text)
        refresh()

    set_task_item.connect("activate", on_set_task)

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

    refresh_item = Gtk.MenuItem(label="Refresh")
    refresh_item.connect("activate", lambda _w: refresh())
    menu.append(refresh_item)

    menu.append(Gtk.SeparatorMenuItem())
    quit_item = Gtk.MenuItem(label="Quit")
    quit_item.connect("activate", lambda _w: Gtk.main_quit())
    menu.append(quit_item)

    menu.show_all()
    indicator.set_menu(menu)

    # Re-read state every 5s so daemon-driven changes show in the header.
    GLib.timeout_add_seconds(5, lambda: (refresh(), True)[1])

    Gtk.main()
