# set power, turn on, turn off, set wavelength
import logging
import time
from abc import abstractmethod
from dataclasses import dataclass

from pyrolab.drivers.lasers.ppcl550 import PPCL550

from pqnstack.base.driver import DeviceClass
from pqnstack.base.driver import DeviceDriver
from pqnstack.base.driver import DeviceInfo
from pqnstack.base.driver import DeviceStatus
from pqnstack.base.driver import log_operation

logger = logging.getLogger(__name__)


@dataclass
class PumpInfo(DeviceInfo):
    active: bool
    wavelength: float
    power: float
    mode: int

class PumpLaser(DeviceDriver):
    DEVICE_CLASS = DeviceClass.LASER

    def __init__(self, name: str, desc: str, address: str) -> None:
        super().__init__(name, desc, address)

        # self.operations[] = self.
        # ^^ set power, turn on/off, set wavelength
        self.operations["set_active"] = self.set_active
        self.operations["set_power"] = self.set_power
        self.operations["set_wavelength"] = self.set_wavelength
        self.operations["set_mode"] = self.set_mode

    @log_operation
    def set_power(self, power: float) -> None: ...
    """Set power to specified power."""

    @log_operation
    def set_wavelength(self, wavelength: float) -> None: ...
    """Set wavelength to specified wavelength."""

    @log_operation
    def set_mode(self, mode: int) -> None: ...
    """Set mode to specified mode"""

    @abstractmethod
    def info(self) -> DeviceInfo: ...

    @abstractmethod
    def close(self) -> None: ...

    @abstractmethod
    def start(self) -> None: ...

class PPCLPumpLaser(PumpLaser):
    def __init__(
        self, name: str, desc: str, address: str, port: str = "COM5"
    ) -> None:
        super().__init__(name, desc, address)
        self.port = port
        # define later

    def close(self) -> None:
        if self._device is not None:
            logger.info("Closing PPCL Pump Laser")
            self._device.off()
            self._device.close()
        self.status = DeviceStatus.OFF

    def start(self) -> None:
        # additional setup for ppcl pump laser specifically
        if self._device is None:
            self._device = PPCL550(self.port)
            self._device.connect(self.port)
            self._device.on()
            time.sleep(10)
            self.status = DeviceStatus.READY
        else:
            logger.info("Initialization fail")

    def info(self) -> PumpInfo:
        return PumpInfo(
            name=self.name,
            desc=self.desc,
            dtype=self.DEVICE_CLASS,
            status=self.status,
            address=self.address,
            active=self.active,
            wavelength=self.wavelength,
            power=self.power,
            mode=self.mode,
        )


    @log_operation
    def set_power(self, power: float) -> None:
        """Set power to specified power (in dBm)."""
        self._device.setPower(power)
        time.sleep(10)

    @log_operation
    def set_wavelength(self, wavelength: float) -> None:
        """Set wavelength to specified wavelength."""
        self._device.setWavelength(wavelength)
        time.sleep(10)

    @log_operation
    def set_mode(self, mode: int) -> None:
        """Set mode to specified mode.

        0: regular, 1: no dither, 2: clean
        """
        self._device.set_mode(mode)
