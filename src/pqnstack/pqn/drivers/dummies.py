import time
from dataclasses import dataclass

from pqnstack.base.instrument import Instrument
from pqnstack.base.instrument import InstrumentInfo
from pqnstack.base.instrument import log_operation
from pqnstack.base.instrument import log_parameter


@dataclass(frozen=True, slots=True)
class DummyInfo(InstrumentInfo):
    param_int: int = 0
    param_str: str = ""
    param_bool: bool = False


@dataclass(slots=True)
class DummyInstrument(Instrument):
    _param_int: int = 2
    _param_str: str = "hello"
    _param_bool: bool = True
    connected: bool = False

    def __post_init__(self) -> None:
        self.parameters = {"param_int", "param_str", "param_bool"}
        self.operations = {
            "double_int": self.double_int,
            "lowercase_str": self.lowercase_str,
            "uppercase_str": self.uppercase_str,
            "toggle_bool": self.toggle_bool,
            "set_half_input_int": self.set_half_input_int,
        }

    @property
    def info(self) -> DummyInfo:
        return DummyInfo(
            name=self.name,
            desc=self.desc,
            hw_address=self.hw_address,
            param_int=self.param_int,
            param_str=self.param_str,
            param_bool=self.param_bool,
        )

    def start(self) -> None:
        self.connected = True

    def close(self) -> None:
        self.connected = False

    @property
    @log_parameter
    def param_int(self) -> int:
        return self._param_int

    @param_int.setter
    @log_parameter
    def param_int(self, value: int) -> None:
        self._param_int = value

    @property
    @log_parameter
    def param_str(self) -> str:
        return self._param_str

    @param_str.setter
    @log_parameter
    def param_str(self, value: str) -> None:
        self._param_str = value

    @property
    @log_parameter
    def param_bool(self) -> bool:
        return self._param_bool

    @param_bool.setter
    @log_parameter
    def param_bool(self, value: bool) -> None:
        self._param_bool = value

    @log_operation
    def double_int(self) -> int:
        self._param_int *= 2
        return self._param_int

    @log_operation
    def set_half_input_int(self, value: int) -> int:
        self._param_int = value // 2
        return self._param_int

    @log_operation
    def lowercase_str(self) -> str:
        self._param_str = self._param_str.lower()
        return self._param_str

    @log_operation
    def uppercase_str(self) -> str:
        self._param_str = self._param_str.upper()
        return self._param_str

    @log_operation
    def toggle_bool(self) -> bool:
        time.sleep(1.4)  # Simulate a long operation
        self._param_bool = not self._param_bool
        return self._param_bool
