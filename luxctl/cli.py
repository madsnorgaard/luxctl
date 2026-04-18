"""Command line interface for luxctl."""

from __future__ import annotations

import argparse
import sys

from . import __version__
from . import state as state_module
from .device import LuxaforError, LuxaforFlag
from .state import State
from .statuses import STATUSES


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="luxctl",
        description="Drive a Luxafor Flag from the command line.",
    )
    parser.add_argument("--version", action="version", version=f"luxctl {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    status = sub.add_parser("status", help="Apply a named status preset.")
    status.add_argument("name", choices=sorted(STATUSES.keys()))
    status.add_argument(
        "--source",
        default="manual",
        help="Source label to record (default: manual).",
    )

    sub.add_parser("list", help="List available status presets.")

    rgb = sub.add_parser("rgb", help="Set an arbitrary static colour.")
    rgb.add_argument("r", type=int)
    rgb.add_argument("g", type=int)
    rgb.add_argument("b", type=int)
    rgb.add_argument("--source", default="manual")

    sub.add_parser("off", help="Turn the light off.")

    sub.add_parser("current", help="Print the most recently applied state.")

    sub.add_parser("tray", help="Launch the system tray indicator.")

    return parser


def _print_current() -> int:
    s = state_module.load()
    if s is None:
        print("luxctl: no state recorded yet")
        return 0
    print(s.describe())
    return 0


def _launch_tray() -> int:
    try:
        from .tray import run_tray
    except ImportError as exc:
        print(
            "luxctl: tray dependencies missing. Install with:\n"
            "  sudo apt install python3-gi gir1.2-ayatanaappindicator3-0.1\n"
            f"({exc})",
            file=sys.stderr,
        )
        return 3
    run_tray()
    return 0


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if args.command == "list":
        width = max(len(name) for name in STATUSES)
        for name in sorted(STATUSES):
            desc = getattr(STATUSES[name], "description", "")
            print(f"  {name:<{width}}  {desc}")
        return 0

    if args.command == "current":
        return _print_current()

    if args.command == "tray":
        return _launch_tray()

    try:
        with LuxaforFlag() as light:
            if args.command == "status":
                STATUSES[args.name](light)
                state_module.save(State(
                    source=args.source,
                    set_at=state_module.now_iso(),
                    status=args.name,
                ))
            elif args.command == "rgb":
                light.static(args.r, args.g, args.b)
                state_module.save(State(
                    source=args.source,
                    set_at=state_module.now_iso(),
                    rgb=(args.r, args.g, args.b),
                ))
            elif args.command == "off":
                light.off()
                state_module.save(State(
                    source="manual",
                    set_at=state_module.now_iso(),
                    status="offline",
                ))
    except LuxaforError as exc:
        print(f"luxctl: {exc}", file=sys.stderr)
        return 1
    except ValueError as exc:
        print(f"luxctl: {exc}", file=sys.stderr)
        return 2

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
