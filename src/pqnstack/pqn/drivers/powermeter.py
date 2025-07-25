import logging
from dataclasses import dataclass

from ThorlabsPM100 import USBTMC
from ThorlabsPM100 import ThorlabsPM100

from pqnstack.base.driver import DeviceClass
from pqnstack.base.driver import DeviceDriver
from pqnstack.base.driver import DeviceInfo
from pqnstack.base.driver import DeviceStatus
from pqnstack.base.driver import log_operation
from pqnstack.base.driver import log_parameter
from pqnstack.base.errors import DeviceNotStartedError

logger = logging.getLogger(__name__)


@dataclass
class PM100DInfo(DeviceInfo):
    power: float
    wavelength: float
    range_auto: bool | None = None
    average_count: int | None = None


class PM100DDevice(DeviceDriver):
    DEVICE_CLASS = DeviceClass.SENSOR

    def __init__(
        self,
        name: str,
        desc: str,
        address: str,
        *,
        use_usbtmc: bool = True,
    ) -> None:
        super().__init__(name, desc, address)
        self.use_usbtmc = use_usbtmc
        self._device: ThorlabsPM100 | None = None

        self.operations["read_power"] = self.read_power
        self.operations["get_wavelength"] = self.get_wavelength
        self.operations["set_wavelength"] = self.set_wavelength

        self.parameters.add("power")
        self.parameters.add("wavelength")

    def start(self) -> None:
        """Connect to the PM100D via USBTMC or VISA and prepare for readings."""
        inst = USBTMC(device=self.address)
        self._device = ThorlabsPM100(inst=inst)
        self.status = DeviceStatus.READY
        logger.info("PM100D connected at %s", self.address)

    def close(self) -> None:
        """Close the connection to the power meter."""
        if self._device is not None:
            self._device.close()
        self.status = DeviceStatus.OFF

    def info(self) -> PM100DInfo:
        """Return current device info, including power and wavelength."""
        return PM100DInfo(
            name=self.name,
            desc=self.desc,
            dtype=self.DEVICE_CLASS,
            status=self.status,
            address=self.address,
            power=self.power,
            wavelength=self.wavelength,
            range_auto=(self._device.sense.power.dc.range.auto if self._device is not None else None),
            average_count=(self._device.sense.average.count if self._device is not None else None),
        )

    @log_operation
    def read_power(self) -> float:
        """Read the current optical power (in W)."""
        return self.power

    @log_operation
    def get_wavelength(self) -> float:
        """Retrieve the meters current operating wavelength (in nm)."""
        return self.wavelength

    @log_operation
    def set_wavelength(self, wavelength: float) -> None:
        """Set a new operating wavelength on the meter (in nm)."""
        self.wavelength = wavelength

    @property
    @log_parameter
    def power(self) -> float:
        """Power reading in watts (uses the SCPI READ command)."""
        if self._device is None:
            msg = "Start the PM100D before reading power"
            raise DeviceNotStartedError(msg)
        return float(self._device.read)

    @property
    @log_parameter
    def wavelength(self) -> float:
        """Get the console operating wavelength (SCPI Sense:Correction:WAVelength)."""
        if self._device is None:
            msg = "Start the PM100D before setting wavelength"
            raise DeviceNotStartedError(msg)
        return float(self._device.sense.correction.wavelength)

    @wavelength.setter
    @log_parameter
    def wavelength(self, wl: float) -> None:
        if self._device is None:
            msg = "Start the PM100D before setting wavelength"
            raise DeviceNotStartedError(msg)
        self._device.sense.correction.wavelength = wl
