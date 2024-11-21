import logging
import math
import sys
import time
from collections import deque
from dataclasses import dataclass
from dataclasses import field
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


@dataclass(slots=True)
class Buffer:
    _buffer: deque[float]
    normalizing: bool = field(default=False)
    _min: float = field(default=float("inf"), init=False)
    _max: float = field(default=float("-inf"), init=False)

    def __post_init__(self) -> None:
        self.flush()

    def __len__(self) -> int:
        return len(self._buffer)

    def flush(self) -> None:
        """Clear all values in the buffer."""
        self._buffer.clear()
        self.min = float("inf")
        self.max = float("-inf")

    def append(self, value: float) -> None:
        self._buffer.append(value)
        if self.normalizing:
            self.min = min(self.min, value)
            self.max = max(self.max, value)

    @property
    def average(self) -> float:
        return sum(self._buffer) / len(self._buffer)

    @property
    def last(self) -> float:
        return self._buffer[-1]


@dataclass(frozen=True, slots=True)
class PolarizationMeasurement:
    h: float
    v: float
    d: float
    a: float

    def __format__(self, spec: str, /) -> str:
        if not spec:
            return self.__repr__()
        return f"{type(self).__name__}(h={self.h:{spec}}, v={self.v:{spec}}, d={self.d:{spec}}, a={self.a:{spec}})"

    @property
    def theta(self) -> float:
        """Return the calculated polarization angle in degrees."""
        cosine = min(math.sqrt(self.h), 1)
        radians = 1 / math.pi * math.acos(cosine)
        sign = math.copysign(1, self.d - self.a)
        return sign * math.degrees(radians)

    @property
    def phi(self) -> float:
        raise NotImplementedError


class Polarimeter(Protocol):
    def read(self) -> PolarizationMeasurement: ...

@dataclass(slots = True)
class ArduinoPolarimeter(Polarimeter):
    board: Arduino = field(default_factory=lambda: Arduino(Arduino.AUTODETECT))
    pins: dict[str, int] = field(default_factory=lambda: dict(zip("hvda", range(4), strict=False)))
    sample_rate: int = 10
    average_width: int = 10
    _buffers: list[Buffer] = field(default_factory=list, init=False)

    def __post_init__(self) -> None:
        self.board.samplingOn(1000 // self.sample_rate)
        for pin in self.pins.values():
            buffer = Buffer(deque(maxlen=self.average_width))
            self._buffers.append(buffer)
            self.board.analog[pin].register_callback(buffer.write)
            self.board.analog[pin].enable_reporting()
        logger.info("Polarimeter started")

    def close(self) -> None:
        if self.board is not None:
            logger.info("Polarimeter stopped")
            self.board.exit()
        self.status = DeviceStatus.OFF

    def reset(self) -> None:
        for buffer in self._buffers:
            buffer.reset()

    def start_normalizing(self) -> None:
        for buffer in self._buffers:
            buffer.reset()
            buffer.normalizing = True

    def stop_normalizing(self) -> None:
        for buffer in self._buffers:
            buffer.normalizing = False

    def read(self) -> PolarizationMeasurement:
        hvda = [buffer.read() for buffer in self._buffers]
        return PolarizationMeasurement(*hvda)
    
class PolarimeterDevice(DeviceDriver, Polarimeter):
    DEVICE_CLASS = DeviceClass.SENSOR

    def __init__(self, name: str, desc: str, address: str) -> None:
        super().__init__(name, desc, address)

        self.operations["read"] = self.read
        self.operations["start_normalizing"] = self.start_normalizing
        self.operations["stop_normalizing"] = self.stop_normalizing
        self.operations["close"] = self.close
        self.operations["start"] = self.start
    
    @log_operation
    def read(self) -> PolarizationMeasurement: ...

    @log_operation
    def reset(self) -> None: ...

    @log_operation
    def start_normalizing(self) -> None: ...
    
    @log_operation
    def stop_normalizing(self) -> None: ...

    @abstractmethod
    def info(self) -> DeviceInfo: ...

    @abstractmethod
    def close(self) -> None: ...

    @abstractmethod
    def start(self) -> None: ...

class ArduinoPolarimeterDevice(PolarimeterDevice): 
    def __init__(self, name: str, desc: str, address: str, ap: ArduinoPolarimeter) -> None:
        super().__init__(name, desc, address)

        self.ap = ap

    def read(self) -> PolarizationMeasurement: 
        return self.ap.read()

    def info(self) -> DeviceInfo:
        return DeviceInfo(
            name = self.name,
            desc = self.desc,
            dtype = self.DEVICE_CLASS,
            status = self.status,
            address = self.address
        )

    def close(self) -> None:
        return self.ap.close()        

    def start(self) -> None:
        self.status = DeviceStatus.READY

