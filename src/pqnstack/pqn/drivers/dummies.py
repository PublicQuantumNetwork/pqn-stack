import time
from dataclasses import dataclass

from pqnstack.base.driver import DeviceDriver, DeviceClass, DeviceInfo, DeviceStatus, log_parameter, log_operation
from pqnstack.base.errors import DeviceNotStartedError


@dataclass
class DummyInfo(DeviceInfo):
    param_int: int
    param_str: str
    param_bool: bool


class DummyInstrument(DeviceDriver):
    DEVICE_CLASS: DeviceClass = DeviceClass.TESTING

    def __init__(self, name: str, desc: str, address: str) -> None:
        super().__init__(name, desc, address)

        self._param_int = 0
        self._param_str = "hello"
        self._param_bool = True

        self.parameters = {"param_int", "param_str", "param_bool"}
        self.operations = {"double_int": self.double_int,
                           "lowercase_str": self.lowercase_str,
                           "uppercase_str": self.uppercase_str,
                           "toggle_bool": self.toggle_bool}

        self.connected = False

    def info(self) -> DummyInfo:
        return DummyInfo(self.name,
                         self.desc,
                         self.address,
                         self.DEVICE_CLASS,
                         self.status,
                         self.param_int,
                         self.param_str,
                         self.param_bool)

    def start(self) -> None:
        self.connected = True
        self.status = DeviceStatus.READY

    def close(self) -> None:
        self.connected = False
        self.status = DeviceStatus.OFF

    @property
    @log_parameter
    def param_int(self) -> int:
        if not self.connected:
            raise DeviceNotStartedError("Device is not connected.")

        return self._param_int

    @param_int.setter
    @log_parameter
    def param_int(self, value: int) -> None:
        if not self.connected:
            raise DeviceNotStartedError("Device is not connected.")

        self._param_int = value

    @property
    @log_parameter
    def param_str(self) -> str:
        if not self.connected:
            raise DeviceNotStartedError("Device is not connected.")

        return self._param_str

    @param_str.setter
    @log_parameter
    def param_str(self, value: str) -> None:
        if not self.connected:
            raise DeviceNotStartedError("Device is not connected.")

        self._param_str = value

    @property
    @log_parameter
    def param_bool(self) -> bool:
        if not self.connected:
            raise DeviceNotStartedError("Device is not connected.")

        return self._param_bool

    @param_bool.setter
    @log_parameter
    def param_bool(self, value: bool) -> None:
        if not self.connected:
            raise DeviceNotStartedError("Device is not connected.")

        self._param_bool = value

    @log_operation
    def double_int(self) -> int:
        if not self.connected:
            raise DeviceNotStartedError("Device is not connected.")

        self._param_int *= 2
        return self._param_int

    @log_operation
    def lowercase_str(self) -> str:
        if not self.connected:
            raise DeviceNotStartedError("Device is not connected.")

        self._param_str = self._param_str.lower()
        return self._param_str

    @log_operation
    def uppercase_str(self) -> str:
        if not self.connected:
            raise DeviceNotStartedError("Device is not connected.")

        self._param_str = self._param_str.upper()
        return self._param_str

    @log_operation
    def toggle_bool(self) -> bool:
        if not self.connected:
            raise DeviceNotStartedError("Device is not connected.")

        time.sleep(1.4)

        self._param_bool = not self._param_bool
        return self._param_bool
