# University of Illinois Urbana-Champaign
# Public Quantum Network
#
# NCSA/Illinois Computes

import logging
import time
from dataclasses import dataclass
from dataclasses import field
from typing import Protocol
from typing import runtime_checkable

import serial
from thorlabs_apt_device import TDC001

from pqnstack.base.errors import DeviceNotStartedError
from pqnstack.base.instrument import Instrument
from pqnstack.base.instrument import InstrumentInfo
from pqnstack.base.instrument import log_parameter

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class RotatorInfo(InstrumentInfo):
    degrees: float = 0.0
    offset_degrees: float = 0.0


@runtime_checkable
@dataclass(slots=True)
class RotatorInstrument(Instrument, Protocol):
    offset_degrees: float = 0.0

    def __post_init__(self) -> None:
        self.operations["move_to"] = self.move_to
        self.operations["move_by"] = self.move_by

        self.parameters.add("degrees")

    @property
    @log_parameter
    def degrees(self) -> float: ...

    @degrees.setter
    @log_parameter
    def degrees(self, degrees: float) -> None: ...

    def move_to(self, angle: float) -> None:
        """Move the rotator to the specified angle."""
        self.degrees = angle

    def move_by(self, angle: float) -> None:
        """Move the rotator by the specified angle."""
        self.degrees += angle


@dataclass(slots=True)
class APTRotator(RotatorInstrument):
    _degrees: float = field(default=0.0, init=False)
    _device: TDC001 = field(init=False, repr=False)
    _encoder_units_per_degree: float = field(default=86384 / 45, init=False, repr=False)

    def start(self) -> None:
        # Additional setup for APT Rotator
        self._device = TDC001(serial_number=self.hw_address)
        offset_eu = round(self.offset_degrees * self._encoder_units_per_degree)

        # NOTE: Velocity units seem to not match position units
        # (Device does not actually move at 1000 deg/s...)
        # 500 is noticeably slower, but more than 1000 doesn't seem faster
        vel = round(1000 * self._encoder_units_per_degree)

        self._device.set_home_params(velocity=vel, offset_distance=offset_eu)
        self._device.set_velocity_params(vel, vel)
        time.sleep(0.5)
        self._wait_for_stop()

    def close(self) -> None:
        if self._device is not None:
            logger.info("Closing APT Rotator")
            self._device.close()

    @property
    def info(self) -> RotatorInfo:
        return RotatorInfo(
            name=self.name,
            desc=self.desc,
            hw_address=self.hw_address,
            hw_status=self._device.status,
            degrees=self.degrees,
            offset_degrees=self.offset_degrees,
        )

    def _wait_for_stop(self) -> None:
        if self._device is None:
            msg = "Start the device before setting parameters"
            raise DeviceNotStartedError(msg)

        try:
            time.sleep(0.5)
            while (
                self._device.status["moving_forward"]
                or self._device.status["moving_reverse"]
                or self._device.status["jogging_forward"]
                or self._device.status["jogging_reverse"]
            ):
                time.sleep(0.1)
        except KeyboardInterrupt:
            self._device.stop(immediate=True)

    @property
    def degrees(self) -> float:
        return self._degrees

    @degrees.setter
    def degrees(self, degrees: float) -> None:
        self._set_degrees_unsafe(degrees)
        self._wait_for_stop()

    def _set_degrees_unsafe(self, degrees: float) -> None:
        self._degrees = degrees
        self._device.move_absolute(int(degrees * self._encoder_units_per_degree))


@dataclass(slots=True)
class SerialRotator(RotatorInstrument):
    _degrees: float = 0.0  # The hardware doesn't support position tracking
    _conn: serial.Serial = field(init=False, repr=False)

    def start(self) -> None:
        self._conn = serial.Serial(self.hw_address, baudrate=115200, timeout=1)
        self._conn.write(b"open_channel")
        self._conn.read(100)
        self._conn.write(b"motor_ready")
        self._conn.read(100)

        self.degrees = self.offset_degrees

    def close(self) -> None:
        self.degrees = 0
        self._conn.close()

    @property
    def info(self) -> RotatorInfo:
        return RotatorInfo(
            name=self.name,
            desc=self.desc,
            hw_address=self.hw_address,
            # hw_status=,
            degrees=self.degrees,
            offset_degrees=self.offset_degrees,
        )

    @property
    def degrees(self) -> float:
        return self._degrees

    @degrees.setter
    def degrees(self, degrees: float) -> None:
        self._conn.write(f"SRA {degrees}".encode())
        self._degrees = degrees
        _ = self._conn.readline().decode()
