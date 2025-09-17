import contextlib
import logging
from dataclasses import dataclass
from dataclasses import field
from typing import Protocol
from typing import runtime_checkable

from ThorlabsPM100 import USBTMC
from ThorlabsPM100 import ThorlabsPM100

from pqnstack.base.instrument import Instrument
from pqnstack.base.instrument import InstrumentInfo
from pqnstack.base.instrument import log_operation

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class PowermeterInfo(InstrumentInfo):
    power: float = 0.0
    wavelength: float = 0.0


@runtime_checkable
@dataclass(slots=True)
class PowermeterInstrument(Instrument, Protocol):
    def __post_init__(self) -> None:
        self.operations["read"] = self.read
        self.operations["set_wavelength"] = self.set_wavelength

    @log_operation
    def read(self) -> PowermeterInfo: ...

    @log_operation
    def set_wavelength(self, value: float) -> None: ...


@dataclass(slots=True)
class PM100D(PowermeterInstrument):
    _device: ThorlabsPM100 = field(init=False, repr=False)

    def start(self) -> None:
        self._device = ThorlabsPM100(USBTMC(device=self.hw_address))
        logger.info("PM100D connected at %s", self.hw_address)  # deal w it

    def close(self) -> None:
        with contextlib.suppress(AttributeError):
            self._device.close()

    def read(self) -> PowermeterInfo:
        power = float(self._device.read)
        wavelength = float(self._device.sense.correction.wavelength)
        return PowermeterInfo(power=power, wavelength=wavelength)

    def set_wavelength(self, value: float) -> None:
        """Set the active correction wavelength in meters.

        Example:
            d = PM100D("/dev/usbtmc0")
            d.set_wavelength(1.55-e6)
        """
        self._device.sense.correction.wavelength = value
