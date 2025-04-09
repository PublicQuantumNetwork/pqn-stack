import logging
import math
from collections import deque
from dataclasses import KW_ONLY
from dataclasses import dataclass
from dataclasses import field
from typing import Protocol
from typing import runtime_checkable

from pyfirmata2 import Arduino

from pqnstack.base.instrument import Instrument
from pqnstack.base.instrument import InstrumentInfo
from pqnstack.base.instrument import log_operation

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
            return 0.0

        if self.max <= self.min:
            return 0.0

        avg = sum(self._buffer) / len(self._buffer)
        return (avg - self.min) / (self.max - self.min)


@dataclass(frozen=True, slots=True)
class PolarizationMeasurement:
    h: float
    v: float
    d: float
    a: float
    _last_theta: float = field(default=0.0, repr=False, kw_only=True)  # HACK: Allow reporting of full 2pi angle

    def __format__(self, spec: str, /) -> str:
        if not spec:
            return self.__repr__()
        return f"{type(self).__name__}(h={self.h:{spec}}, v={self.v:{spec}}, d={self.d:{spec}}, a={self.a:{spec}})"

    @property
    def theta(self) -> float:
        """Return the calculated polarization angle in degrees."""
        if self.h + self.v == 0 or self.d + self.a == 0:
            return 0.0

        # Read polarization angle from photodiodes
        h = self.h / (self.h + self.v)
        radians = math.acos(math.sqrt(h))
        sign = math.copysign(1, self.a - self.d)
        degrees = sign * math.degrees(radians) % 180

        # Shift based on previous angle to allow full 0-360 range
        shifted = self._last_theta // 180
        prev_wedge = self._last_theta % 180 // 60
        new_wedge = degrees // 60

        if abs(new_wedge - prev_wedge) > 1:
            shifted = not shifted

        if shifted:
            degrees += 180

        return degrees % 360

    @property
    def phi(self) -> float:
        raise NotImplementedError


@dataclass(frozen=True, slots=True)
class PolarimeterInfo(InstrumentInfo):
    pass


@runtime_checkable
@dataclass(slots=True)
class PolarimeterInstrument(Instrument, Protocol):
    def __post_init__(self) -> None:
        self.operations["read"] = self.read
        self.operations["reset"] = self.reset
        self.operations["start_normalizing"] = self.start_normalizing
        self.operations["stop_normalizing"] = self.stop_normalizing

    @property
    def info(self) -> PolarimeterInfo: ...

    @log_operation
    def read(self) -> PolarizationMeasurement: ...

    @log_operation
    def reset(self) -> None: ...

    @log_operation
    def start_normalizing(self) -> None: ...

    @log_operation
    def stop_normalizing(self) -> None: ...


@dataclass(slots=True)
class ArduinoPolarimeter(PolarimeterInstrument):
    sample_rate: int = 10
    average_width: int = 10
    _: KW_ONLY
    board: Arduino = field(default_factory=lambda: Arduino(Arduino.AUTODETECT))
    pins: dict[str, int] = field(default_factory=lambda: dict(zip("hvda", range(4), strict=False)))
    _buffers: list[Buffer] = field(default_factory=list, init=False)
    _last_theta: float = field(default=0.0, init=False, repr=False)  # HACK: Allow reporting of full 2pi angle

    def start(self) -> None:
        if not self.board:
            self.board = Arduino(Arduino.AUTODETECT)
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
