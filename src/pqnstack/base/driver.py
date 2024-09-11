# University of Illinois Urbana-Champaign
# Public Quantum Network
#
# NCSA/Illinois Computes

from abc import ABC
from abc import abstractmethod
from dataclasses import dataclass
from collections.abc import Callable
from enum import Enum, auto


class DeviceClass(Enum):
    SENSOR = auto()
    MOTOR = auto()
    TEMPCTRL = auto()
    TIMETAGR = auto()
    TESTING = auto()


# FIXME: What is the exact difference between on and idle?
#  I know there is a semantic difference and how we thing of those terms,
#  but in practice in the code, is there a real difference?
class DeviceStatus(Enum):
    NOINIT = "not uninitialized"
    FAIL = "fail"
    OFF = "off"
    IDLE = "idle"
    ON = "on"


# TODO: Add address here. I cannot imagine having a device without an address.
#  Might not always be an ip address but it must have some sort of adress
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

        # FIXME: dtype handling is very ugly right now.
        dtype = specs["dtype"]
        if isinstance(dtype, DeviceClass):
            self.dtype = dtype
        else:
            if dtype not in DeviceClass.__members__:
                msg = f"Invalid device class: {dtype}"
                raise ValueError(msg)
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

    @abstractmethod
    def close(self, **kwargs) -> None:
        pass
