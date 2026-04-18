"""Shared diagnostic helpers used by 'luxctl doctor' and richer error messages.

Each check is a pure function returning (ok: bool, hint: str). Hints are
written for users who have never read the source code.
"""

from __future__ import annotations

import grp
import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

VENDOR_HEX = "04d8"
PRODUCT_HEX = "f372"


@dataclass
class Check:
    name: str
    ok: bool
    detail: str = ""
    hint: str = ""


def lsusb_finds_flag() -> Check:
    if not shutil.which("lsusb"):
        return Check("lsusb available", False, hint="install usbutils: sudo apt install usbutils")
    try:
        out = subprocess.check_output(["lsusb"], timeout=2).decode()
    except subprocess.SubprocessError as exc:
        return Check("lsusb runs", False, detail=str(exc))
    if f"{VENDOR_HEX}:{PRODUCT_HEX}".lower() in out.lower():
        return Check("Luxafor Flag visible to lsusb", True)
    return Check(
        "Luxafor Flag visible to lsusb",
        False,
        hint="device not detected. Plug it in, or try a different USB port / cable.",
    )


def hidraw_node_for_flag() -> tuple[Check, str | None]:
    """Return (check, /dev/hidrawN path or None)."""
    sys_root = Path("/sys/class/hidraw")
    if not sys_root.exists():
        return Check("hidraw subsystem present", False, hint="kernel without hidraw support"), None
    for node in sorted(sys_root.iterdir()):
        modalias = node / "device" / "modalias"
        if not modalias.exists():
            continue
        try:
            text = modalias.read_text().lower()
        except OSError:
            continue
        if f"v0000{VENDOR_HEX}p0000{PRODUCT_HEX}" in text:
            dev = Path("/dev") / node.name
            return Check(f"hidraw node found at {dev}", True), str(dev)
    return Check(
        "hidraw node found",
        False,
        hint="kernel sees no Luxafor hidraw device. Replug the Flag.",
    ), None


def hidraw_perms(dev_path: str | None) -> Check:
    if not dev_path:
        return Check("hidraw permissions", False, hint="no hidraw node to check")
    p = Path(dev_path)
    if not p.exists():
        return Check("hidraw permissions", False, hint=f"{dev_path} disappeared")
    st = p.stat()
    mode = st.st_mode & 0o777
    try:
        gname = grp.getgrgid(st.st_gid).gr_name
    except KeyError:
        gname = str(st.st_gid)
    user_groups = {grp.getgrgid(g).gr_name for g in os.getgroups()}
    can_open = (mode & 0o006) or (gname in user_groups and mode & 0o060)
    if can_open:
        return Check(f"{dev_path} writable (mode {oct(mode)} group {gname})", True)
    return Check(
        f"{dev_path} writable",
        False,
        detail=f"mode {oct(mode)} group {gname}",
        hint=(
            "install the udev rule: "
            "sudo cp udev/99-luxafor.rules /etc/udev/rules.d/ && "
            "sudo udevadm control --reload-rules && "
            "sudo udevadm trigger --action=change /sys/class/hidraw/" + p.name
        ),
    )


def hidapi_lib_present() -> Check:
    try:
        import hid  # noqa: F401
        return Check("Python `hid` package importable", True)
    except ImportError as exc:
        return Check(
            "Python `hid` package importable",
            False,
            detail=str(exc),
            hint=(
                "install the hidapi C library and the Python binding: "
                "sudo apt install libhidapi-hidraw0 libhidapi-libusb0 && "
                "pip install hid"
            ),
        )


def can_open_flag() -> Check:
    """Tries to open the device. Closes immediately if successful."""
    try:
        import hid
        d = hid.Device(vid=int(VENDOR_HEX, 16), pid=int(PRODUCT_HEX, 16))
        d.close()
        return Check("luxctl can open the Flag", True)
    except Exception as exc:  # noqa: BLE001
        return Check(
            "luxctl can open the Flag",
            False,
            detail=str(exc),
            hint=(
                "open failed. The previous checks tell you which step to fix. "
                "If they all pass, another process may already hold the device "
                "(check `pgrep -af luxctl`)."
            ),
        )


def diagnose_device() -> list[Check]:
    """Run the device-related checks in order. Used by both doctor and the
    LuxaforError message path."""
    checks: list[Check] = []
    checks.append(hidapi_lib_present())
    checks.append(lsusb_finds_flag())
    raw_check, dev_path = hidraw_node_for_flag()
    checks.append(raw_check)
    checks.append(hidraw_perms(dev_path))
    checks.append(can_open_flag())
    return checks


def first_failure_hint(checks: list[Check]) -> str:
    """Return the hint of the first failed check, for use in error messages."""
    for c in checks:
        if not c.ok and c.hint:
            return c.hint
    return ""
