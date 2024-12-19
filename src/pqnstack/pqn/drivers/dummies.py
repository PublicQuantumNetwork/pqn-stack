import time
from dataclasses import dataclass

from pqnstack.base.driver import DeviceClass
from pqnstack.base.driver import DeviceDriver
from pqnstack.base.driver import DeviceInfo
from pqnstack.base.driver import DeviceStatus
from pqnstack.base.driver import log_operation
from pqnstack.base.driver import log_parameter


@dataclass
class DummyInfo(DeviceInfo):
    param_int: int
    param_str: str
    param_bool: bool


class DummyInstrument(DeviceDriver):
    DEVICE_CLASS: DeviceClass = DeviceClass.TESTING

    def __init__(self, name: str, desc: str, address: str) -> None:
        super().__init__(name, desc, address)

        self._param_int: int = 2
        self._param_str: str = "hello"
        self._param_bool: bool = True

        self.parameters = {"param_int", "param_str", "param_bool"}
        self.operations = {
            "double_int": self.double_int,
            "lowercase_str": self.lowercase_str,
            "uppercase_str": self.uppercase_str,
            "toggle_bool": self.toggle_bool,
            "set_half_input_int": self.set_half_input_int,
        }

        self.connected = False

    def info(self) -> DummyInfo:
        return DummyInfo(
            self.name,
            self.desc,
            self.address,
            self.DEVICE_CLASS,
            self.status,
            self.param_int,
            self.param_str,
            self.param_bool,
        )

    def start(self) -> None:
        self.connected = True
        self.status = DeviceStatus.READY

    def close(self) -> None:
        self.connected = False
        self.status = DeviceStatus.OFF

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
        self.param_int *= 2
        return self.param_int

    @log_operation
    def set_half_input_int(self, value: int) -> int:
        self.param_int = value // 2
        return self.param_int

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
