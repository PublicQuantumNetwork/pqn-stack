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

import sys
import time
import warnings
import pyvisa

from pqnstack.base.errors import DeviceNotStartedError
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
    def set_wavelength(self, wavelength: float) -> None: ...


@dataclass(slots=True)
class PAX1000IR2(ThorlabsPolarimeterInstrument):
    self._calc_on = "SENS:CALC 1"
    self._rot_on = "INP:ROT:STAT 1"
    self._calc_off = "SENS:CALC 0"
    self._rot_off = "INP:ROT:STAT 0"
    self._q_calc = "SENS:CALC?"
    self._q_rot = "INP:ROT:STAT?"
    self._q_latest = "SENS:DATA:LAT?"
    
    self._q_wav = "SENS:CORR:WAV?"

    def start(self) -> None:
        self._rm = pyvisa.ResourceManager('@py')
        self._device = rm.list_resources(hw_address)
        if not self._device:
            logger.info("No USB VISA instrument found")


    def read_data(self) -> ThorlabsPolarimeterInfo:
        str_data_values = self._write_query(self._device, self._q_latest)
        list_data_values = self._parse_data(str_data_values)

        # for each value in list, set the appropriate InstrumentInfo value to the value in list
        theta_val = values[9]
        eta_val = values[10]
        dop_val = values[11]
        power_val = values[12]
        
        info_data_values = ThorlabsPolarimeterInfo(theta = theta_val, eta = eta_val, dop = dop_val, power = power_val)
        return info_data_values


    def read_wavelength(self) -> float:
        

    def set_wavelength(self, wavelength: float): None:


    def close(self) -> None:
        if self._device is not None:
            logger.info("Closing Thorlabs Polarimeter")
            self._device._calc_off()
            self._device._rot_off()
            if self._q_calc:
                logger.info("Calc function failed to close")
            if self._q_rot:
                logger.info("Rot function failed to close")


     # internal functions below
     def _write_command(instrument: any, command: str) -> None:
        instrument.write(f"{command}\n")

     def _write_query(instrument: any, command: str) -> str:
        instrument.write(f"{command}\n")
        return instrument.read().strip()

     def _write_and_confirm(
        instrument: Any,
        set_command: str,
        query_command: str,
        expected_prefix: Union[str, int, float],
        sleep_seconds: float = 0.05,
     ) -> Tuple[bool, str]:
        write_command(instrument, set_command)

        last_value: str = ""
        expected_str = str(expected_prefix)

        last_value = query_string(instrument, query_command).strip()
        if last_value.startswith(expected_str):
            return True, last_value
        time.sleep(sleep_seconds)
        return False, last_value

     def parse_data(data: str) -> List[Union[float, str]]:
        str_values = [p for p in data.replace(";", ",").split(",") if p != ""]
        values: List[Union[float, str]] = []
        for value in str_values:
            try:
                values.append(float(token))
            except Exception:
                values.append(token)
        return values
