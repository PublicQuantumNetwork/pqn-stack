import logging
import math
from abc import abstractmethod
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

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class Buffer:
    _buffer: deque[float]
    normalizing: bool = field(default=False)
    min: float = field(default=float("inf"), init=False)
    max: float = field(default=float("-inf"), init=False)

    def __post_init__(self) -> None:
        self.clear()

    def __len__(self) -> int:
        return len(self._buffer)

    def clear(self) -> None:
        """Clear all values in the buffer."""
        self._buffer.clear()
        self.min = float("inf")
        self.max = float("-inf")

    def append(self, value: float) -> None:
        self._buffer.append(value)
        if self.normalizing:
            self.min = min(self.min, value)
            self.max = max(self.max, value)

    def read(self) -> float:
        if len(self._buffer) == 0:
            return 0
        return sum(self._buffer) / len(self._buffer)


@dataclass(frozen=True, slots=True)
class PolarizationMeasurement:
    h: float
    v: float
    d: float
    a: float
    _last_theta: float = field(default=0.0, repr=False)  # HACK: Allow reporting of full 2pi angle

    def __format__(self, spec: str, /) -> str:
        if not spec:
            return self.__repr__()
        return f"{type(self).__name__}(h={self.h:{spec}}, v={self.v:{spec}}, d={self.d:{spec}}, a={self.a:{spec}})"

    @property
    def theta(self) -> float:
        """Return the calculated polarization angle in degrees."""

        # Primary branch for inverse trig function
        def _h_deg():
            h = self.h / (self.h + self.v)
            cosine = min(math.sqrt(h), 1)
            radians = 1 / math.pi * math.acos(cosine)
            sign = math.copysign(1, self.a - self.d)
            return sign * math.degrees(radians)

        # Alternate branch for inverse trig for access to full 2pi range.
        # Requires caller to pass a `_last_theta` value.
        # NOTE: The branch jump may not be smooth in both directions.
        def _a_deg():
            a = self.a / (self.a + self.d)
            sine = min(math.sqrt(a), 1)
            radians = 1 / math.pi * math.asin(sine) - 1 / 4
            sign = math.copysign(1, self.h - self.v)
            return sign * math.degrees(radians)

        lth = self._last_theta % 360
        if 0 <= lth < 45:
            degrees = _h_deg()
        elif 45 <= lth < 180:
            degrees = _a_deg() + 180
        elif 180 <= lth < 270:
            degrees = _h_deg() + 180
        else:
            degrees = _a_deg() + 360
        return degrees % 360

    @property
    def phi(self) -> float:
        raise NotImplementedError


class Polarimeter(Protocol):
    def read(self) -> PolarizationMeasurement: ...


@dataclass(slots=True)
class ArduinoPolarimeter(Polarimeter):
    board: Arduino = field(default_factory=lambda: Arduino(Arduino.AUTODETECT))
    pins: dict[str, int] = field(default_factory=lambda: dict(zip("hvda", range(4), strict=False)))
    sample_rate: int = 10
    average_width: int = 10
    _buffers: list[Buffer] = field(default_factory=list, init=False)
    _last_theta: float = field(default=0.0, init=False, repr=False)  # HACK: Allow reporting of full 2pi angle

    def __post_init__(self) -> None:
        self.board.samplingOn(1000 // self.sample_rate)
        for pin in self.pins.values():
            buffer = Buffer(deque(maxlen=self.average_width))
            self._buffers.append(buffer)
            self.board.analog[pin].register_callback(buffer.append)
            self.board.analog[pin].enable_reporting()
        logger.info("Polarimeter started")

    def close(self) -> None:
        if self.board is not None:
            logger.info("Polarimeter stopped")
            self.board.exit()

    def reset(self) -> None:
        self._last_theta = 0.0
        for buffer in self._buffers:
            buffer.clear()

    def start_normalizing(self) -> None:
        self._last_theta = 0.0
        for buffer in self._buffers:
            buffer.clear()
            buffer.normalizing = True

    def stop_normalizing(self) -> None:
        for buffer in self._buffers:
            buffer.normalizing = False

    def read(self) -> PolarizationMeasurement:
        hvda = [buffer.read() for buffer in self._buffers]
        pm = PolarizationMeasurement(*hvda, _last_theta=self._last_theta)
        self._last_theta = pm.theta
        return pm


class PolarimeterDevice(DeviceDriver):
    DEVICE_CLASS = DeviceClass.SENSOR

    def __init__(self, name: str, desc: str, address: str) -> None:
        super().__init__(name, desc, address)

        self.operations["read"] = self.read
        self.operations["reset"] = self.reset
        self.operations["start_normalizing"] = self.start_normalizing
        self.operations["stop_normalizing"] = self.stop_normalizing

    @abstractmethod
    @log_operation
    def read(self) -> PolarizationMeasurement: ...

    @abstractmethod
    @log_operation
    def reset(self) -> None: ...

    @abstractmethod
    @log_operation
    def start_normalizing(self) -> None: ...

    @abstractmethod
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

    def reset(self) -> None:
        self.ap.reset()

    def start_normalizing(self) -> None:
        self.ap.start_normalizing()

    def stop_normalizing(self) -> None:
        self.ap.stop_normalizing()

    def info(self) -> DeviceInfo:
        return DeviceInfo(
            name=self.name, desc=self.desc, dtype=self.DEVICE_CLASS, status=self.status, address=self.address
        )

    def close(self) -> None:
        self.ap.close()
        self.status = DeviceStatus.OFF

    def start(self) -> None:
        self.status = DeviceStatus.READY
