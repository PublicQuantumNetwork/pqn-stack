import contextlib
import logging
import math
from abc import abstractmethod
from collections import deque
from dataclasses import dataclass
from dataclasses import field
from typing import Protocol
from typing import cast

import usbtmc
from pyfirmata2 import Arduino

from pqnstack.base.driver import DeviceClass
from pqnstack.base.driver import DeviceDriver
from pqnstack.base.driver import DeviceInfo
from pqnstack.base.driver import DeviceStatus
from pqnstack.base.driver import log_operation
from pqnstack.base.driver import log_parameter
from pqnstack.base.errors import DeviceNotStartedError

logger = logging.getLogger(__name__)


@dataclass
class PAX1000Info(DeviceInfo):
    power_watts: float
    azimuth_deg: float
    ellipticity_deg: float
    phi_deg: float


class PAX1000IR2Device(DeviceDriver):
    DEVICE_CLASS = DeviceClass.SENSOR

    def __init__(
        self,
        name: str,
        desc: str,
        address: str,
        wavelength_nm: float | None = None,
    ):
        super().__init__(name, desc, address)
        self.wavelength_nm = wavelength_nm
        self._inst: usbtmc.Instrument | None = None

        self.operations["read_power"] = self.read_power
        self.operations["read_azimuth"] = self.read_azimuth
        self.operations["read_ellipticity"] = self.read_ellipticity
        self.operations["read_theta_phi"] = self.read_theta_phi

        self.parameters.add("power_watts")
        self.parameters.add("azimuth_deg")
        self.parameters.add("ellipticity_deg")
        self.parameters.add("phi_deg")

    def start(self) -> None:
        """Open USBTMC connection and set wavelength if provided."""
        logger.info("Connecting to PAX1000IR2 at %s", self.address)
        self._inst = usbtmc.Instrument(self.address)
        self._inst.timeout = 5000  # ms
        if self.wavelength_nm is not None:
            cmd = f"SOURce:CORRection:WAVelength {self.wavelength_nm}"
            self._inst.write(cmd)
        self.status = DeviceStatus.READY

    def close(self) -> None:
        """Close the USBTMC session."""
        if self._inst is not None:
            logger.info("Closing PAX1000IR2 connection")
            with contextlib.suppress(Exception):
                self._inst.close()
        self.status = DeviceStatus.OFF

    def info(self) -> PAX1000Info:
        """Return all current readings in one info object."""
        p = self.read_power()
        azi = self.read_azimuth()
        ell = self.read_ellipticity()
        phi, theta = self.read_theta_phi()
        return PAX1000Info(
            name=self.name,
            desc=self.desc,
            dtype=self.DEVICE_CLASS,
            status=self.status,
            address=self.address,
            power_watts=p,
            azimuth_deg=azi,
            ellipticity_deg=ell,
            phi_deg=phi,
        )

    def _query(self, cmd: str) -> str:
        if self._inst is None:
            msg = "Device not started"
            raise DeviceNotStartedError(msg)
        raw = cast("str", self._inst.ask(cmd))
        return raw.strip()

    @log_parameter
    def read_power(self) -> float:
        """Read optical power in watts."""
        resp = self._query("MEASure:POWer:DC?")
        return float(resp)

    @log_parameter
    def read_azimuth(self) -> float:
        """Read polarization azimuth (θ) in degrees."""
        data = self._query("SENSE1:DATA:LATEST?")
        theta_str = data.split(",")[0]
        return float(theta_str)

    @log_parameter
    def read_ellipticity(self) -> float:
        """Read polarization ellipticity (η) in degrees."""
        data = self._query("SENSE1:DATA:LATEST?")
        eta_str = data.split(",")[1]
        return float(eta_str)

    @log_parameter
    def read_theta_phi(self) -> tuple[float, float]:
        """Return (phi, theta) where phi = 2·η and theta is the SCPI θ, giving spherical coordinate style angles."""
        theta = self.read_azimuth()
        eta = self.read_ellipticity()
        phi = 2 * eta
        return phi, theta


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
    _last_theta: float = field(default=0.0, repr=False, kw_only=True)

    def __format__(self, spec: str, /) -> str:
        if not spec:
            return self.__repr__()
        return f"{type(self).__name__}(h={self.h:{spec}}, v={self.v:{spec}}, d={self.d:{spec}}, a={self.a:{spec}})"

    @property
    def theta(self) -> float:
        """Return the calculated polarization angle in degrees."""
        if self.h + self.v == 0 or self.d + self.a == 0:
            return 0.0

        h = self.h / (self.h + self.v)
        radians = math.acos(math.sqrt(h))
        sign = math.copysign(1, self.a - self.d)
        degrees = sign * math.degrees(radians) % 180

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


class Polarimeter(Protocol):
    def read(self) -> PolarizationMeasurement: ...


@dataclass(slots=True)
class ArduinoPolarimeter(Polarimeter):
    board: Arduino = field(default_factory=lambda: Arduino(Arduino.AUTODETECT))
    pins: dict[str, int] = field(default_factory=lambda: dict(zip("hvda", range(4), strict=False)))
    sample_rate: int = 10
    average_width: int = 10
    _buffers: list[Buffer] = field(default_factory=list, init=False)
    _last_theta: float = field(default=0.0, init=False, repr=False)

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
            name=self.name,
            desc=self.desc,
            dtype=self.DEVICE_CLASS,
            status=self.status,
            address=self.address,
        )

    def close(self) -> None:
        self.ap.close()
        self.status = DeviceStatus.OFF

    def start(self) -> None:
        self.status = DeviceStatus.READY
