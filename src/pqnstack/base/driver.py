# University of Illinois Urbana-Champaign
# Public Quantum Network
#
# NCSA/Illinois Computes

from abc import ABC
from abc import abstractmethod
from enum import Enum
from typing import Callable
from typing import Optional


class DeviceDriver(ABC):
    def __init__(self, specs: dict) -> None:
        # Self-documenting features
        self.name = specs["name"]
        self.desc = specs["desc"]
        self.dtype = DeviceClass[specs["dtype"]]
        self.status = DeviceStatus.NOINIT

        # Executable functionalities
        self.provides = specs["provides"]
        self.executable: dict[str, Callable] = {}

        # Tunable device parameters across multiple experiments
        self.params = specs["params"]

        # Call the available implementation of `setup`
        self.setup(specs)

    def info(self, attr: str, **kwargs) -> dict:
        return {"name": self.name, "desc": self.desc, "dtype": self.dtype.value, "status": self.status.value}

    @abstractmethod
    def setup(self, specs: dict) -> None:
        pass

    @abstractmethod
    def exec(self, seq: str, **kwargs) -> Optional[dict]:
        pass


class DeviceClass(Enum):
    SENSOR = 1
    MOTOR = 2
    TEMPCTRL = 3
    TIMETAGR = 4


class DeviceStatus(Enum):
    NOINIT = "not uninitialized"
    FAIL = "fail"
    OFF = "off"
    IDLE = "idle"
    ON = "on"
