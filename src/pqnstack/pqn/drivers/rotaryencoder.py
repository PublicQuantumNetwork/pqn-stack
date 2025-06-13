import atexit
from dataclasses import dataclass
from dataclasses import field

import serial


@dataclass(slots=True)
class SerialRotaryEncoder:
    label: str
    address: str
    offset_degrees: float = 0.0
    _controller: serial.Serial = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self._controller = serial.Serial(self.address, baudrate=115200, timeout=1)
        self._controller.write(b"open_channel")
        self._controller.read(100)
        self._controller.write(b"ready")
        self._controller.read(100)

        atexit.register(self.cleanup)

    def cleanup(self) -> None:
        self._controller.close()

    def read(self) -> float:
        self._controller.write(b"ANGLE?\n")
        angle = self._controller.readline().decode().strip()
        return float(angle) + self.offset_degrees
