"""Named status presets.

Each status is a function that takes a `LuxaforFlag` and configures it.
Add your own — just decorate with `@register(name, description)`.
"""

from __future__ import annotations

from typing import Callable, Dict

from .device import LuxaforFlag, PATTERN_POLICE, PATTERN_RAINBOW

Status = Callable[[LuxaforFlag], None]
STATUSES: Dict[str, Status] = {}


def register(name: str, description: str = "") -> Callable[[Status], Status]:
    def decorator(fn: Status) -> Status:
        fn.description = description  # type: ignore[attr-defined]
        STATUSES[name] = fn
        return fn
    return decorator


# --- Everyday statuses ---------------------------------------------------

@register("available", "Solid green. Come talk to me.")
def available(light: LuxaforFlag) -> None:
    light.static(0, 255, 0)


@register("busy", "Solid red. Please do not interrupt.")
def busy(light: LuxaforFlag) -> None:
    light.static(255, 0, 0)


@register("meeting", "Solid blue. On a call.")
def meeting(light: LuxaforFlag) -> None:
    light.static(0, 0, 255)


@register("brb", "Yellow fade. Back shortly.")
def brb(light: LuxaforFlag) -> None:
    light.fade(255, 200, 0, speed=40)


@register("offline", "Off. End of day.")
def offline(light: LuxaforFlag) -> None:
    light.off()


# --- Developer moods -----------------------------------------------------

@register("deep-work", "Slow purple fade. Heads down.")
def deep_work(light: LuxaforFlag) -> None:
    light.fade(128, 0, 180, speed=80)


@register("pairing", "Cyan solid. Collaborating live.")
def pairing(light: LuxaforFlag) -> None:
    light.static(0, 200, 200)


@register("rubber-duck", "Yellow fade. Debugging in progress.")
def rubber_duck(light: LuxaforFlag) -> None:
    light.fade(255, 220, 0, speed=60)


@register("deploying", "Rainbow wave. Please hold.")
def deploying(light: LuxaforFlag) -> None:
    light.pattern(PATTERN_RAINBOW, repeat=3)


# --- The funny ones ------------------------------------------------------

@register("stressed", "Police siren. Everything is on fire.")
def stressed(light: LuxaforFlag) -> None:
    light.pattern(PATTERN_POLICE, repeat=10)


@register("on-fire", "Rapid red strobe. Production is down.")
def on_fire(light: LuxaforFlag) -> None:
    light.strobe(255, 0, 0, speed=5, repeat=30)


@register("coffee", "Orange fade. Refilling caffeine.")
def coffee(light: LuxaforFlag) -> None:
    light.fade(255, 100, 0, speed=50)


@register("lunch", "Yellow slow strobe. Eating, do not enter.")
def lunch(light: LuxaforFlag) -> None:
    light.strobe(255, 200, 0, speed=40, repeat=5)


# --- Work-from-home specials --------------------------------------------

@register("kid-incoming", "Pink pulse. Small human approaching.")
def kid_incoming(light: LuxaforFlag) -> None:
    light.fade(255, 100, 150, speed=20)


@register("party", "Rainbow fast. Ship it Friday.")
def party(light: LuxaforFlag) -> None:
    light.pattern(PATTERN_RAINBOW, repeat=10)


@register("dnd", "Red strobe. Absolutely do not disturb.")
def dnd(light: LuxaforFlag) -> None:
    light.strobe(255, 0, 0, speed=30, repeat=10)
