import atexit
from dataclasses import dataclass
from dataclasses import field

import serial


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
