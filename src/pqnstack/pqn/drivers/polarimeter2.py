import math
import sys
import time
from collections import deque
from dataclasses import dataclass
from dataclasses import field
from typing import Dict
from typing import Protocol

from pyfirmata2 import Arduino


class Polarimeter(Protocol):
    def theta(self): ...
    def phi(self): ...


@dataclass
class DataBuffer:
    maxlen: int = 10
    min: float = float("inf")
    max: float = -float("inf")
    is_calibrating: bool = False

    def __post_init__(self):
        self._buffer: deque[float] = deque(maxlen=self.maxlen)

    def reset(self):
        self._buffer.clear()
        self.min = float("inf")
        self.max = float("-inf")

    def append(self, value: float):
        self._buffer.append(value)
        if self.is_calibrating:
            self.min = min(self.min, value)
            self.max = max(self.max, value)

    @property
    def average(self) -> float:
        return sum(self._buffer) / self.maxlen

    @property
    def last(self) -> float:
        return self._buffer[-1]

@dataclass
class ArduinoPolarimeter(Polarimeter):
    #device: Arduino = Arduino(Arduino.AUTODETECT)
    pins: Dict[str, int] = field(default_factory=lambda: {k: v for k, v in zip("hvda", range(4))})
    sample_rate: int = 10
    buffer_maxlen: int = 10
    buffers: Dict[str, DataBuffer] = field(default_factory=dict)

    def __post_init__(self):
        self.device = Arduino(Arduino.AUTODETECT)
        self.device.samplingOn(1000 / self.sample_rate)

        for pol, pin in self.pins.items():
            buffer = DataBuffer(maxlen=self.buffer_maxlen)
            self.buffers[pol] = buffer
            self.device.analog[pin].register_callback(buffer.append)
            self.device.analog[pin].enable_reporting()

    def reset(self):
        for pol, buffer in self.buffers.items():
            buffer.reset()

    def set_calibration(self, do_calibrate: bool):
        for pol, buffer in self.buffers.items():
            buffer.is_calibrating = do_calibrate

    def _read(self, detector: str):
        return self.buffers[detector].last

    def _average(self, detector: str):
        return self.buffers[detector].average

    @property
    def h(self) -> float:
        return self._average("h")

    @property
    def v(self) -> float:
        return self._average("v")

    @property
    def d(self) -> float:
        return self._average("d")

    @property
    def a(self) -> float:
        return self._average("a")
    @property
    def theta(self) -> float:
        """Returns the calculated polarization angle in degrees."""

        norm = {}
        for pol, buffer in self.buffers.items():
            buf_min = buffer.min
            buf_max = buffer.max
            buf_avg = buffer.average

            if buf_max == buf_min:
                norm[pol] = 0
            else:
                norm[pol] = abs((buf_avg - buf_min) / (buf_max - buf_min))

        cosine = min(math.sqrt(norm["h"]), 1)
        radians = math.acos(cosine)
        sign = math.copysign(1, norm["d"] - norm["a"])
        return sign * math.degrees(radians)

    @property
    def phi(self) -> float:
        # WARN: Not currently implemented
        return 0

    @property
    def summary(self) -> str:
        """A summary of the polarimeter data."""
        return f"h: {self.h:.2f} v: {self.v:.2f} d: {self.d:.2f} a: {self.a:.2f} theta: {self.theta:.2f} phi: {self.phi:.2f}"


if __name__ == "__main__":
    polarimeter = ArduinoPolarimeter()
    polarimeter.set_calibration(True)

    try:
        while True:
            sys.stdout.write("\r" + polarimeter.summary)
            sys.stdout.flush()
            time.sleep(0.1)
    except KeyboardInterrupt:
        sys.stdout.write("\n")

