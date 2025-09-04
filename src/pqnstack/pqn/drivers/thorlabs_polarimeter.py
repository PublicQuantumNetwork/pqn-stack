# University of Illinois Urbana-Champaign
# Public Quantum Network
#
# NCSA/Illinois Computes

import logging
from dataclasses import dataclass
from typing import Protocol
from typing import runtime_checkable

import pyvisa

from pqnstack.base.instrument import Instrument
from pqnstack.base.instrument import InstrumentInfo
from pqnstack.base.instrument import log_parameter

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class ThorlabsPolarimeterInfo(InstrumentInfo):
    theta: float = 0.0
    eta: float = 0.0
    wavelength: float = 1550.0
    power: float = 0.0
    dop: float = 0.0


@runtime_checkable
@dataclass(slots=True)
class ThorlabsPolarimeterInstrument(Instrument, Protocol):
    def __post_init__(self) -> None:
        self.operations["read"] = self.read
        self.operations["set_wavelength"] = self.set_wavelength

    @property
    @log_parameter
    def read(self) -> ThorlabsPolarimeterInfo: ...

    @property
    @log_parameter
    def wavelength(self) -> float: ...

    @wavelength.setter
    @log_parameter
    def wavelength(self, wavelength: float) -> None: ...


@dataclass(slots=True)
class PAX1000IR2(ThorlabsPolarimeterInstrument):
    def start(self) -> None:
        # try to set calc + rot on, then check if they're on
        # if they are, return, if not, turn everything off + log crash

        _rm = pyvisa.ResourceManager("@py")
        self._device = _rm.list_resources(self.hw_address)
        if not self._device:
            # deal w it
            return

        self._write("SENS:CALC 1")
        self._write("INP:ROT:STAT 1")

    def read_data(self) -> ThorlabsPolarimeterInfo:
        str_data_values = self._query("SENS:DATA:LAT?")
        values = self._parse_data(str_data_values)

        return ThorlabsPolarimeterInfo(theta=values[9], eta=values[10], dop=values[11], power=values[12])

    @property
    def wavelength(self) -> float:
        return self._query("SENS:CORR:WAV?")

    @wavelength.setter
    def wavelength(self, wavelength: float) -> None:
        self._write(f"SENS:CORR:WAV {wavelength}")

    def close(self) -> None:
        # deal w it
        self._write("SENS:CALC 0")
        self._write("INP:ROT:STAT 0")

    # internal functions below

    def _query(self, command: str) -> str:
        self._device.write(f"{command}\n")
        return self._device.read().strip()

    def _write(self, command: str) -> None:
        command_name, value = command.split(" ")

        self._device.write(command)
        confirm = self._query(command_name + "?")

        # if confirm != value:
        # deal w it

    def parse_data(self, data: str) -> list[float | str]:
        # double check w/ raw data format
        str_values = [p for p in data.replace(";", ",").split(",") if p != ""]
        values: list[float | str] = []
        for value in str_values:
            try:
                values.append(float(value))
            except ValueError:
                values.append(value)
        return values
