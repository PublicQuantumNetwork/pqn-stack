# University of Illinois Urbana-Champaign
# Public Quantum Network
#
# NCSA/Illinois Computes

import logging
from dataclasses import dataclass
from dataclasses import field
from typing import Protocol, cast
from typing import runtime_checkable

from pyvisa import ResourceManager
from pyvisa.resources import USBInstrument
from usb.core import USBError

from pqnstack.base.instrument import Instrument
from pqnstack.base.instrument import InstrumentInfo
from pqnstack.base.instrument import log_parameter

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class ThorlabsPolarimeterInfo(InstrumentInfo):
    theta: float = 0.0
    eta: float = 0.0
    power: float = 0.0
    dop: float = 0.0
    wavelength: float = 0.0


@runtime_checkable
@dataclass(slots=True)
class ThorlabsPolarimeterInstrument(Instrument, Protocol):
    def __post_init__(self) -> None:
        self.operations["read"] = self.read
        self.parameters.add("wavelength")

    @log_parameter
    def read(self) -> ThorlabsPolarimeterInfo: ...

    @property
    @log_parameter
    def wavelength(self) -> float: ...

    @wavelength.setter
    @log_parameter
    def wavelength(self, value: float) -> None: ...


@dataclass(slots=True)
class PAX1000IR2(ThorlabsPolarimeterInstrument):
    _device: USBInstrument = field(init=False, repr=False)

    def start(self) -> None:
        # try to set calc + rot on, then check if they're on
        # if they are, return, if not, turn everything off + log crash

        _rm = ResourceManager()
        _resources = _rm.list_resources(f"?*{self.hw_address}?*::INSTR")
        if not _resources:
            # bad hw_address
            # deal w it
            return

        try:
            self._device = cast("USBInstrument", _rm.open_resource(_resources[0]))
        except USBError:
            # resource is busy
            # log error
            raise

        self._device.write("SENS:CALC 1")
        self._device.write("INP:ROT:STAT 1")

    def close(self) -> None:
        # deal w it
        try:
            self._device.write("SENS:CALC 0")
            self._device.write("INP:ROT:STAT 0")
            self._device.close()
        except AttributeError:
            # Nothing to do if `start` hasn't been called yet
            pass

    def read(self) -> ThorlabsPolarimeterInfo:
        # See https://www.thorlabs.com/_sd.cfm?fileName=MTN007790-D04.pdf&partumber=PAX1000IR2
        data_keys = (
            "revs",
            "timestamp",
            "paxOpMode",
            "paxFlags",
            "paxTIARange",
            "adcMin",
            "adcMax",
            "revTime",
            "misAdj",
            "theta",
            "eta",
            "DOP",
            "Ptotal",
        )
        data = self._device.query("SENS:DATA:LAT?").strip().split(",")

        hw_status: dict[str, str] = dict(zip(data_keys, data, strict=True))
        theta, eta, dop, power = (float(val) for val in data[9:13])

        return ThorlabsPolarimeterInfo(
            name=self.name,
            desc=self.desc,
            hw_address=self.hw_address,
            hw_status=hw_status,
            theta=theta,
            eta=eta,
            dop=dop,
            power=power,
            wavelength=self.wavelength,
        )

    @property
    def wavelength(self) -> float:
        return float(self._device.query("SENS:CORR:WAV?"))

    @wavelength.setter
    def wavelength(self, value: float) -> None:
        self._device.write(f"SENS:CORR:WAV {value}")
