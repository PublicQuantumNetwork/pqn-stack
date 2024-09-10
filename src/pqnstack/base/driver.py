# University of Illinois Urbana-Champaign
# Public Quantum Network
#
# NCSA/Illinois Computes

from abc import ABC
from abc import abstractmethod
from dataclasses import dataclass
from collections.abc import Callable
from enum import Enum


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


@dataclass
class DeviceInfo:
    name: str
    desc: str
    dtype: DeviceClass
    status: DeviceStatus


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
        DeviceInfo(name=self.name, desc=self.desc, dtype=self.dtype, status=self.status)

    @abstractmethod
    def setup(self, specs: dict) -> None:
        pass

    @abstractmethod
    def exec(self, seq: str, **kwargs) -> None | dict:
        pass
