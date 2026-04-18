"""Shared pytest fixtures."""

from __future__ import annotations

import pytest

from luxctl.device import LuxaforFlag


class FakeHidDevice:
    """Records every byte string written to it. No real USB involved."""

    def __init__(self) -> None:
        self.writes: list[bytes] = []
        self.closed = False

    def write(self, data: bytes) -> int:
        self.writes.append(bytes(data))
        return len(data)

    def close(self) -> None:
        self.closed = True


@pytest.fixture
def fake_hid() -> FakeHidDevice:
    return FakeHidDevice()


@pytest.fixture
def light(fake_hid: FakeHidDevice) -> LuxaforFlag:
    return LuxaforFlag(device=fake_hid)
