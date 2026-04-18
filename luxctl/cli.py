"""Command line interface for luxctl."""

from __future__ import annotations

import argparse
import sys

from . import __version__
from . import config as config_module
from . import state as state_module
from .controller import Controller
from .device import LuxaforError
from .state import State
from .statuses import STATUSES, load_from_config


def _register_custom_presets() -> None:
    """Pick up [presets.*] blocks from config.toml so completion + dispatch
    see them. Silent if config doesn't exist or has no presets."""
    try:
        raw = config_module.load_config()
    except Exception:
        return
    presets = raw.get("presets", {})
    if isinstance(presets, dict) and presets:
        load_from_config(presets)


_register_custom_presets()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="luxctl",
        description="Drive a Luxafor Flag from the command line, "
        "and aggregate presence from multiple sources.",
    )
    parser.add_argument("--version", action="version", version=f"luxctl {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    status = sub.add_parser("status", help="Apply a named status preset.")
    status.add_argument("name", choices=sorted(STATUSES.keys()))
    status.add_argument(
        "--source",
        default="cli",
        help="Source label to record (default: cli).",
    )
    status.add_argument(
        "--task",
        default=None,
        help="Set the active task at the same time.",
    )

    sub.add_parser("list", help="List available status presets.")

    rgb = sub.add_parser("rgb", help="Set an arbitrary static colour.")
    rgb.add_argument("r", type=int)
    rgb.add_argument("g", type=int)
    rgb.add_argument("b", type=int)
    rgb.add_argument("--source", default="cli")

    sub.add_parser("off", help="Turn the light off.")

    sub.add_parser("current", help="Print the most recently applied state.")

    task = sub.add_parser("task", help="Set or clear the active task text.")
    task_group = task.add_mutually_exclusive_group(required=True)
    task_group.add_argument("text", nargs="?", help="The task text.")
    task_group.add_argument("--clear", action="store_true", help="Clear the active task.")

    sub.add_parser("tray", help="Launch the system tray indicator.")

    logs = sub.add_parser("logs", help="Tail the transition log.")
    logs.add_argument("-n", "--lines", type=int, default=20)
    logs.add_argument("-f", "--follow", action="store_true")

    sub.add_parser("daemon", help="Run the presence-aggregator daemon.")

    sub.add_parser("init", help="First-run interactive setup wizard.")
    sub.add_parser("doctor", help="Diagnose installation and config issues.")

    install = sub.add_parser("install-service", help="Install + enable + start the systemd user service.")
    install.add_argument("--no-start", action="store_true", help="Install + enable, but do not start now.")
    install.add_argument("--no-enable", action="store_true", help="Install only, do not enable on login.")
    sub.add_parser("uninstall-service", help="Stop, disable, and remove the systemd user service.")
    sub.add_parser("service-status", help="Print whether the systemd user service is installed/active.")

    stats = sub.add_parser("stats", help="Time spent per status from the transition log.")
    stats.add_argument("--week", action="store_true", help="Last 7 days instead of today.")
    stats.add_argument("--days", type=int, default=0, help="Last N days (overrides --week).")

    from .slack_cli import add_slack_subparser
    add_slack_subparser(sub)

    # Optional: tab-completion if argcomplete is installed.
    try:
        import argcomplete  # type: ignore[import-untyped]
        argcomplete.autocomplete(parser)
    except ImportError:
        pass

    return parser


def _print_current() -> int:
    s = state_module.load()
    if s is None:
        print("luxctl: no state recorded yet")
        return 0
    print(s.describe())
    return 0


def _set_task(text: str | None, clear: bool) -> int:
    if clear:
        state_module.update(active_task=None)
        print("luxctl: active task cleared")
    else:
        state_module.update(active_task=text)
        print(f"luxctl: active task set to {text!r}")
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


def _launch_daemon() -> int:
    try:
        from .daemon import run_daemon
    except ImportError as exc:
        print(f"luxctl: daemon unavailable ({exc})", file=sys.stderr)
        return 3
    run_daemon()
    return 0


def _tail_logs(lines: int, follow: bool) -> int:
    from .sinks.log import _default_log_path

    path = _default_log_path()
    if not path.exists():
        print(f"luxctl: no log at {path}")
        return 0
    import subprocess

    cmd = ["tail", f"-n{lines}"]
    if follow:
        cmd.append("-f")
    cmd.append(str(path))
    return subprocess.call(cmd)


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

    if args.command == "task":
        return _set_task(args.text, args.clear)

    if args.command == "tray":
        return _launch_tray()

    if args.command == "daemon":
        return _launch_daemon()

    if args.command == "logs":
        return _tail_logs(args.lines, args.follow)

    if args.command == "slack":
        return args.handler(args)

    if args.command == "init":
        from .init_cli import run as init_run
        return init_run()

    if args.command == "doctor":
        from .doctor import run as doctor_run
        return doctor_run()

    if args.command == "install-service":
        from .service import install as svc_install
        return svc_install(enable=not args.no_enable, start=not args.no_start)

    if args.command == "uninstall-service":
        from .service import uninstall as svc_uninstall
        return svc_uninstall()

    if args.command == "service-status":
        from .service import status as svc_status
        return svc_status()

    if args.command == "stats":
        from .stats import run as stats_run
        period = "week" if args.week else "today"
        return stats_run(period=period, days=args.days)

    try:
        with Controller() as ctrl:
            if args.command == "status":
                # Only pass active_task if the user actually used --task,
                # so omitting it preserves the existing task instead of clearing it.
                kw = {"source": args.source}
                if args.task is not None:
                    kw["active_task"] = args.task
                results = ctrl.apply_status(args.name, **kw)
                for name, err in results:
                    if err:
                        print(f"luxctl: sink {name} failed: {err}", file=sys.stderr)
            elif args.command == "rgb":
                ctrl.apply_rgb(args.r, args.g, args.b, source=args.source)
            elif args.command == "off":
                ctrl.apply_status("offline", source="cli")
    except LuxaforError as exc:
        print(f"luxctl: {exc}", file=sys.stderr)
        return 1
    except ValueError as exc:
        print(f"luxctl: {exc}", file=sys.stderr)
        return 2

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
