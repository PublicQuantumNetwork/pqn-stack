import atexit
from dataclasses import dataclass
from dataclasses import field
from typing import Protocol
from typing import runtime_checkable

import serial


@runtime_checkable
class RotaryEncoderInstrument(Protocol):
    def read(self) -> float: ...


@dataclass(slots=True)
class SerialRotaryEncoder:
    label: str
    address: str
    offset_degrees: float = 0.0
    _conn: serial.Serial = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self._conn = serial.Serial(self.address, baudrate=115200, timeout=1)
        self._conn.write(b"open_channel")
        self._conn.read(100)
        self._conn.write(b"ready")
        self._conn.read(100)

        atexit.register(self.close)

    def close(self) -> None:
        self._conn.close()

    def read(self) -> float:
        self._conn.write(b"ANGLE?\n")
        angle = self._conn.readline().decode().strip()
        return float(angle) + self.offset_degrees


@dataclass(slots=True)
class MockRotaryEncoder:
    """Mock rotary encoder for terminal input when hardware is not available."""

    theta: float = 0.0

    def read(self) -> float:
        return self.theta
