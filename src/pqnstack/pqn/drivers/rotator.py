# University of Illinois Urbana-Champaign
# Public Quantum Network
#
# NCSA/Illinois Computes

import logging
import time
import serial
from abc import abstractmethod
from dataclasses import dataclass
from typing import Any

from thorlabs_apt_device import TDC001

from pqnstack.base.driver import DeviceClass
from pqnstack.base.driver import DeviceDriver
from pqnstack.base.driver import DeviceInfo
from pqnstack.base.driver import DeviceStatus
from pqnstack.base.driver import log_operation
from pqnstack.base.driver import log_parameter
from pqnstack.base.errors import DeviceNotStartedError

logger = logging.getLogger(__name__)


@dataclass
class RotatorInfo(DeviceInfo):
    offset_degrees: float
    degrees: float
    encoder_units_per_degree: float | None = None
    rotator_status: dict[str, Any] | None = None


class Rotator(DeviceDriver):
    DEVICE_CLASS = DeviceClass.MOTOR

    def __init__(self, name: str, desc: str, address: str) -> None:
        super().__init__(name, desc, address)

        self.operations["move_to"] = self.move_to
        self.operations["move_by"] = self.move_by

    @log_operation
    def move_to(self, angle: float) -> None:
        """Move the rotator to the specified angle."""
        self.degrees = angle

    @log_operation
    def move_by(self, angle: float) -> None:
        """Move the rotator by the specified angle."""
        self.degrees += angle

    @abstractmethod
    def info(self) -> DeviceInfo: ...

    @abstractmethod
    def close(self) -> None: ...

    @abstractmethod
    def start(self) -> None: ...


class APTRotator(Rotator):
    def __init__(
        self, name: str, desc: str, address: str, offset_degrees: float = 0.0, *, block_while_moving: bool = True
    ) -> None:
        super().__init__(name, desc, address)

        self.block_while_moving = block_while_moving

        self.offset_degrees = offset_degrees
        self.encoder_units_per_degree = 86384 / 45

        # Instrument does not seem to keep track of its position.
        self._degrees = 0.0
        self._device: TDC001 | None = None

        self.parameters.add("degrees")

    def close(self) -> None:
        if self._device is not None:
            logger.info("Closing APT Rotator")
            self._device.close()
        self.status = DeviceStatus.OFF

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
        self.status = DeviceStatus.READY

    def info(self) -> RotatorInfo:
        return RotatorInfo(
            name=self.name,
            desc=self.desc,
            dtype=self.DEVICE_CLASS,
            status=self.status,
            address=self.address,
            offset_degrees=self.offset_degrees,
            encoder_units_per_degree=self.encoder_units_per_degree,
            degrees=self.degrees,
            rotator_status=self._device.status if self._device is not None else None,
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
                continue
        except KeyboardInterrupt:
            self._device.stop(immediate=True)

    @property
    @log_parameter
    def degrees(self) -> float:
        return self._degrees

    @degrees.setter
    @log_parameter
    def degrees(self, degrees: float) -> None:
        if self._device is None:
            msg = "Start the device before setting parameters"
            raise DeviceNotStartedError(msg)

        self._degrees = degrees
        self.status = DeviceStatus.BUSY
        self._device.move_absolute(int(degrees * self.encoder_units_per_degree))
        if self.block_while_moving:
            self._wait_for_stop()
        self.status = DeviceStatus.READY


class HBRotator(Rotator):
    def __init__(self, name: str, desc: str, address: str, offset_degrees: float = 0.0) -> None:
        super().__init__(self, name, desc, address)
        self.offset_degrees = offset_degrees
        self._degrees = 0
        

        self.parameters.add("degrees")

    def close(self) -> None:
        if self._ard is not None:
            logger.info("Closing house-built rotator")
            self.ard.close()
        self.status = DeviceStatus.OFF

    def start(self) -> None:
        self.ard = serial.Serial(address, baudrate = 11520, timeout = 1)
        self.ard.write(b'open_channel')
        self.ard.read(100)
        self.ard.write(b'motor_ready')
        self.ard.read(100)
        if self.block_while_moving:
            time.sleep(0.5)
            self.wait_for_stop()
        self.status = DeviceStatus.READY

    def info(self) -> RotatorInfo:
        return RotatorInfo(
            name=self.name,
            desc=self.desc,
            dtype=self.DEVICE_CLASS,
            status=self.status,
            address=self.address,
            offset_degrees=self.offset_degrees,
            degrees=self.degrees,
            rotator_status = self.DeviceStatus)
    
    @property
    @log_parameter
    def degrees(self) -> float:
        return self._degrees

    @degrees.setter
    @log_parameter
    def degrees(self, degrees: float) -> None:
        if self._device is None:
            msg = "Start the device before setting parameters"
            raise DeviceNotStartedError(msg)
        self._degrees = degrees
        self.status = DeviceStatus.BUSY
        self.move_to(degrees)

    def move_to(degrees: float) -> str:
        tmp = angle - self._degrees
        temp = f"SRA {angle}"
        self.ard.write(temp.encode())
        print("sra done")
        return self.ard.readline().decode()






     

if __name__ == "__main__":
    rotator = HBRotator("test", "testing if it works", "/dev/ttyUSB0")
    rotator.start()
    rotator.degrees(25)
    rotator.degrees()
    rotator.close()
   
