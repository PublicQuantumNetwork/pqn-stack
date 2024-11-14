import logging
import math
import time
from abc import abstractmethod
from collections import deque
from dataclasses import dataclass, field
from typing import Protocol

from pyfirmata2 import Arduino
from pqnstack.base.driver import DeviceClass
from pqnstack.base.driver import DeviceDriver
from pqnstack.base.driver import DeviceInfo
from pqnstack.base.driver import DeviceStatus
from pqnstack.base.driver import log_operation
from pqnstack.base.driver import log_parameter
from pqnstack.base.errors import DeviceNotStartedError

logger = logging.getLogger(__name__)


class Polarimeter(Protocol):
    def theta(self) -> float: ...
    def phi(self) -> float: ...


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
class ArduinoPolarimeterInfo(DeviceInfo):
    pins: dict[str, int] 
    sample_rate: int
    buffer_maxlen: int
    buffers: dict[str, DataBuffer]


class ArduinoPolarimeter(Polarimeter, DeviceDriver):
    DEVICE_CLASS = DeviceClass.SENSOR

    def __init__(self, name: str, desc: str, address: str, pins = field(default_factory=lambda: {k: v for k, v in zip("hvda", range(4), strict=False)}) , sample_rate: int = 10, buffer_maxlen: int = 10, buffers = field(default_factory=dict), *args, **kwargs) -> None:
        super().__init__(name, desc, address)

        self.pins = pins
        self.sample_rate = sample_rate
        self.buffer_maxlen = buffer_maxlen
        self.buffers = buffers
        
        self.device: Arduino | None = None
        self.parameters.add("theta")
        self.parameters.add("phi")

        self.operations["reset"] = self.reset
        self.operations["set_calibration"] = self.set_calibration

    def close(self) -> None:
        if self.device is not None:
            logger.info("Closing Arduino Polarimeter")
            self.device.exit()
        self.status = DeviceStatus.OFF

    def start(self) -> None:
        self.device = Arduino(Arduino.AUTODETECT)
        self.device.samplingOn(1000 / self.sample_rate)

        for pol, pin in self.pins.items():
            buffer = self.buffers[pol]
            self.device.analog[pin].register_callback(buffer.append)
            self.device.analog[pin].enable_reporting()

        self.status = DeviceStatus.READY

    def info(self) -> PolarimeterInfo:
        return PolarimeterInfo(
            name=self.name,
            desc=self.desc,
            dtype=self.DEVICE_CLASS,
            status=self.status,
            address=self.address,
            sample_rate=self.sample_rate,
            buffer_maxlen=self.buffer_maxlen,
            buffers=self.buffers
        )

    def reset(self):
        for buffer in self.buffers.values():
            buffer.reset()

    def set_calibration(self, do_calibrate: bool):
        for buffer in self.buffers.values():
            buffer.is_calibrating = do_calibrate

    @property
    @log_parameter
    def h(self) -> float:
        return self._average("h")

    @property
    @log_parameter
    def v(self) -> float:
        return self._average("v")

    @property
    @log_parameter
    def d(self) -> float:
        return self._average("d")

    @property
    @log_parameter
    def a(self) -> float:
        return self._average("a")

    @property
    @log_parameter
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
    @log_parameter
    def phi(self) -> float:
        # WARN: Not currently implemented
        return 0

    @property
    def summary(self) -> str:
        """A summary of the polarimeter data."""
        return f"h: {self.h:.2f} v: {self.v:.2f} d: {self.d:.2f} a: {self.a:.2f} theta: {self.theta:.2f} phi: {self.phi:.2f}"

    def _average(self, detector: str) -> float:
        return self.buffers[detector].average


if __name__ == "__main__":
    polarimeter = ArduinoPolarimeter(name="Polarimeter", desc="Arduino Polarimeter", address="00:00:00:00:00:00")
    polarimeter.set_calibration(True)

    try:
        while True:
            sys.stdout.write("\r" + polarimeter.summary)
            sys.stdout.flush()
            time.sleep(0.1)
    except KeyboardInterrupt:
        sys.stdout.write("\n")
