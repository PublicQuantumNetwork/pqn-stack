# University of Illinois Urbana-Champaign
# Public Quantum Network
#
# NCSA/Illinois Computes

"""Probably want to write a 2 power meter code?

functions: read each powermeter and output in the same way? Return two PowermeterInfo classes??

"""

# review all imports at the end
import logging
import time # may not be necessary
from dataclasses import dataclass
from dataclasses import field # may not be necessary
from typing import Protocol
from typing import runtime_checkable

from ThorlabsPM100 import ThorlabsPM100, USBTMC

from pqnstack.base.errors import DeviceNotStartedError
from pqnstack.base.instrument import Instrument
from pqnstack.base.instrument import InstrumentInfo
from pqnstack.base.instrument import log_parameter

logger = logging.getLogger(__name__)

@dataclass(frozen=True, slots=True)                     
class PowermeterInfo(InstrumentInfo):
    power_W: float = 0.0
    wavelength_nm: float = 1550.0

@runtime_checkable
@dataclass(slots=True)
class PowermeterInstrument(Instrument, Protocol):
    def __post_init__(self) -> None:
        self.operations["read"] = self.read
        self.parameters.add("wavelength_nm")
        self.parameters.add("power_W")

    @property
    @log_parameter
    def read(self) -> PowermeterInfo: ...

    @property
    @log_parameter
    def power_W(self) -> float: ...

    @property
    @log_parameter
    def wavelength_nm(self) -> float: ...

    @wavelength_um.setter
    @log_parameter
    def wavelength_nm(self, value: float) -> None: ...

@dataclass(slots=True)
class PM100D(PowermeterInstrument):
    _device: ThorlabsPM100 = field(init=False)
    def start(self) -> None:
        # connect to device
        """Connect to the PM100D via USBTMC or VISA and prepare for readings."""
        inst = USBTMC(device=self.hw_address)
        self._device = ThorlabsPM100(inst=inst)
        logger.info("PM100D connected at %s", self.hw_address) # deal w it

    def close (self) -> None:
        # turn off powermeter
        """Close the connection to the power meter."""
        if self._device is not None:
            self._device.close()

    def read(self) -> PowermeterInfo:
        power = float(self._device.read)
        wavelength = float(self._device.sense.correction.wavelength)
        return PowermeterInfo(power_W = power, wavelength_nm = wavelength * (1e9))

    @property
    def power_W(self) -> float:
        return float(self._device.read)

    @property
    def wavelength_nm(self) -> float:
        return float(self._device.sense.correction.wavelength)

    @wavelength_nm.setter
    def wavelength_nm(self, value: float) -> None:
        self._device.sense.correction.wavelength = value
