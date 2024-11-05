# University of Illinois Urbana-Champaign
# Public Quantum Network
#
# NCSA/Illinois Computes

import time
import atexit
from dataclasses import dataclass

import serial
from thorlabs_apt_device import TDC001

from pqnstack.base.driver import DeviceClass
from pqnstack.base.driver import DeviceDriver
from pqnstack.base.driver import DeviceStatus
from pqnstack.base.driver import DeviceInfo
from pqnstack.base.driver import log_operation
from pqnstack.base.driver import log_parameter

@dataclass
class RotatorInfo(DeviceInfo):
    offset_degrees: float
    degrees: float
    encoder_units_per_degree: float | None = None
    rotator_status: dict | None = None


class Rotator(DeviceDriver):
    def __init__(self, name: str, desc: str, address: str | int, *args, **kwargs) -> None:
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
        

class APTRotator(Rotator):

    DEVICE_CLASS = DeviceClass.MOTOR

    def __init__(self, name: str, desc: str, address: str | int, offset_degrees: float = 0.0, block_while_moving: bool = True) -> None:
        super().__init__(name, desc, address)

        self.block_while_moving = block_while_moving

        self.offset_degrees = offset_degrees
        self.encoder_units_per_degree = (86384 / 45)
        
        # Instrumet does not seem to keep track of its position.
        self._degrees = 0
        self._device = None

    def close(self) -> None:
        super().close()
        self._device.close()
        self.status = DeviceStatus.OFF

    def start(self) -> None:
        super().start()
        # Additional setup for APT Rotator
        self._device = TDC001(serial_number=self.address)
        offset_eu = round(self.offset_degrees * self.encoder_units_per_degree)
        
        # NOTE: Velocity units seem to not match position units
        # (Device does not actually move at 1000 deg/s...)
        # 500 is noticibly slower, but more than 1000 doesnt seem faster
        vel = round(1000 * self.encoder_units_per_degree)
        self._device.set_home_params(velocity=vel, offset_distance=offset_eu)
        self._device.set_velocity_params(vel, vel)
        if self.block_while_moving:
            time.sleep(0.5)
            self._sleep_while_moving()
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
            rotator_status=self._device.status,
        )
    
    def _sleep_while_moving(self):
        try:
            moving = lambda : self._device.status["moving_forward"] or self._device.status["moving_reverse"] or self._device.status["jogging_forward"] or self._device.status["jogging_reverse"]
            time.sleep(0.5)
            while (moving()):
                continue
        except KeyboardInterrupt as e:
            self._device.stop(True)


    @property
    @log_parameter
    def degrees(self) -> float:
        return self._degrees
    
    @degrees.setter
    @log_parameter
    def degrees(self, degrees: float) -> None:
        self._degrees = degrees
        self.status = DeviceStatus.BUSY
        self._device.move_absolute(int(degrees * self.encoder_units_per_degree))
        if self.block_while_moving:
            self._sleep_while_moving()
        self.status = DeviceStatus.READY
        return degrees
        
        