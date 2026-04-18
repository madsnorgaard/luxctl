"""Named status presets.

Two ways to add a preset:

1. In Python, here in this file: define a function and decorate with
   `@register(name, description)`.

2. In config.toml without writing Python:

       [presets.coding]
       static = [50, 200, 50]
       description = "Solid green-ish, hands on the keyboard."

       [presets.urgent]
       strobe = [255, 0, 0]
       speed = 5
       repeat = 30

   Supported keys per preset: `static`, `fade`, `strobe`, `wave`,
   `pattern` (1-8), plus `speed`, `repeat`, `wave_type` modifiers.
   `load_from_config` reads these and registers them at startup.
"""

from __future__ import annotations

from typing import Any, Callable, Dict

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


# --- TOML-driven presets ------------------------------------------------

def _build_from_spec(spec: dict[str, Any]) -> Status:
    """Turn a {static|fade|strobe|wave|pattern: ...} dict into a callable."""
    if "static" in spec:
        r, g, b = spec["static"]
        return lambda light: light.static(int(r), int(g), int(b))
    if "fade" in spec:
        r, g, b = spec["fade"]
        speed = int(spec.get("speed", 30))
        return lambda light: light.fade(int(r), int(g), int(b), speed=speed)
    if "strobe" in spec:
        r, g, b = spec["strobe"]
        speed = int(spec.get("speed", 20))
        repeat = int(spec.get("repeat", 5))
        return lambda light: light.strobe(int(r), int(g), int(b), speed=speed, repeat=repeat)
    if "wave" in spec:
        r, g, b = spec["wave"]
        wave_type = int(spec.get("wave_type", 1))
        speed = int(spec.get("speed", 30))
        repeat = int(spec.get("repeat", 3))
        return lambda light: light.wave(int(r), int(g), int(b),
                                        wave_type=wave_type, speed=speed, repeat=repeat)
    if "pattern" in spec:
        pattern_id = int(spec["pattern"])
        repeat = int(spec.get("repeat", 5))
        return lambda light: light.pattern(pattern_id, repeat=repeat)
    raise ValueError(
        "preset spec must contain one of: static, fade, strobe, wave, pattern"
    )


def load_from_config(presets: dict[str, dict[str, Any]]) -> list[str]:
    """Register every preset from config. Returns the list of names registered.

    Re-registering an existing name overrides it (lets users tweak the
    built-ins from config without editing Python)."""
    names: list[str] = []
    for name, spec in presets.items():
        if not isinstance(spec, dict):
            continue
        try:
            fn = _build_from_spec(spec)
        except (KeyError, ValueError, TypeError):
            continue
        fn.description = spec.get("description", "(custom preset)")  # type: ignore[attr-defined]
        STATUSES[name] = fn
        names.append(name)
    return names
