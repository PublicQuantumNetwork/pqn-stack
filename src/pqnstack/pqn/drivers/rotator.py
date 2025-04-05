# University of Illinois Urbana-Champaign
# Public Quantum Network
#
# NCSA/Illinois Computes

import logging
import time
from dataclasses import dataclass
from dataclasses import field
from typing import Any
from typing import Protocol
from typing import runtime_checkable

import serial
from thorlabs_apt_device import TDC001

from pqnstack.base.driver import Driver
from pqnstack.base.driver import require_started
from pqnstack.base.errors import DeviceNotStartedError
from pqnstack.base.instrument import InstrumentClass
from pqnstack.base.instrument import InstrumentInfo
from pqnstack.base.instrument import NetworkInstrument
from pqnstack.base.instrument import log_operation
from pqnstack.base.instrument import log_parameter

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class RotatorInfo(InstrumentInfo):
    degrees: float = 0.0
    offset_degrees: float = 0.0
    encoder_units_per_degree: float = 1.0
    rotator_status: dict[str, Any] = field(default_factory=dict)


@runtime_checkable
@dataclass(slots=True)
class RotatorDriver(Driver, Protocol):
    offset_degrees: float = 0.0
    encoder_units_per_degree: float = 1.0

    @property
    @require_started
    def degrees(self) -> float: ...

    @degrees.setter
    @require_started
    def degrees(self, degrees: float) -> None: ...


class RotatorInstrument(NetworkInstrument[RotatorDriver]):
    DEVICE_CLASS = InstrumentClass.MOTOR

    def __init__(self, name: str, desc: str, driver: RotatorDriver) -> None:
        super().__init__(name, desc, driver)

        self.operations["move_to"] = self.move_to
        self.operations["move_by"] = self.move_by

        self.parameters.add("degrees")

    @property
    def info(self) -> RotatorInfo:
        return RotatorInfo(
            dtype=self.INSTRUMENT_CLASS,
            status=self.status,
            address=self.driver.address,
            degrees=self.degrees,
            offset_degrees=self.driver.offset_degrees,
            encoder_units_per_degree=self.driver.encoder_units_per_degree,
            hardware_status=self.driver.status,
        )

    @property
    @log_parameter
    def degrees(self) -> float:
        return self.driver.degrees

    @log_operation
    def move_to(self, angle: float) -> None:
        """Move the rotator to the specified angle."""
        self.driver.degrees = angle

    @log_operation
    def move_by(self, angle: float) -> None:
        """Move the rotator by the specified angle."""
        self.driver.degrees += angle


@dataclass(slots=True)
class APTRotator(RotatorDriver):
    block_while_moving: bool = True
    _device: TDC001 = field(init=False, repr=False)
    _degrees: float = 0.0

    def __post_init__(self) -> None:
        self.encoder_units_per_degree = 86384 / 45

    def start(self) -> None:
        # Additional setup for APT Rotator
        self._device = TDC001(serial_number=self.address)
        offset_eu = round(self.offset_degrees * self.encoder_units_per_degree)

        # NOTE: Velocity units seem to not match position units
        # (Device does not actually move at 1000 deg/s...)
        # 500 is noticeably slower, but more than 1000 doesn't seem faster
        vel = round(1000 * self.encoder_units_per_degree)

        self._device.set_home_params(velocity=vel, offset_distance=offset_eu)
        self._device.set_velocity_params(vel, vel)
        if self.block_while_moving:
            time.sleep(0.5)
            self._wait_for_stop()

    def close(self) -> None:
        if self._device is not None:
            logger.info("Closing APT Rotator")
            self._device.close()

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
        self._degrees = degrees
        self._device.move_absolute(int(degrees * self.encoder_units_per_degree))
        if self.block_while_moving:
            self._wait_for_stop()


@dataclass(slots=True)
class SerialRotator(RotatorDriver):
    _degrees: float = 0.0  # The hardware doesn't support position tracking
    _device: serial.Serial = field(init=False, repr=False)

    def start(self) -> None:
        self._device = serial.Serial(self.address, baudrate=115200, timeout=1)
        self._device.write(b"open_channel")
        self._device.read(100)
        self._device.write(b"motor_ready")
        self._device.read(100)

        self.degrees = self.offset_degrees

    def close(self) -> None:
        self.degrees = 0
        self._device.close()

    @property
    def degrees(self) -> float:
        return self._degrees

    @degrees.setter
    def degrees(self, degrees: float) -> None:
        self._device.write(f"SRA {degrees}".encode())
        self._degrees = degrees
        _ = self._device.readline().decode()
