# University of Illinois Urbana-Champaign
# Public Quantum Network
#
# NCSA/Illinois Computes

import logging
import inspect
from abc import ABC
from typing import Any
from abc import abstractmethod
from dataclasses import dataclass
from collections.abc import Callable
from enum import Enum, auto
from typing import get_type_hints

logger = logging.getLogger(__name__)


# TODO: Add value validator. We should probably be checking if the value is within the expected range.
class Parameter(property):
    """
    Inherits from property. Lets us automatically detect the parameters a driver has, adds logging and type checking.
    If the setter is called with a wrong type, it will raise a TypeError.
    
    Example:
    ```
    class MyDriver(DeviceDriver):
        ...
        
        @Parameter
        def my_param(self) -> int:
            return self.ask("get_my_param_from_device")
            
        @my_param.setter
        def my_param(self, value: int) -> None:
            self.write("set_my_param_from_device", value)
    ```
    """

    def __get__(self, instance: Any, owner: type | None = None) -> Any:
        ret = super().__get__(instance, owner)
        # This functions might be called by normal python functioning without using a parameter, 
        # when this happens instance is None and can crash the logging. 
        if instance is not None:
            logger.info(f"Getting {self.fget.__name__} from {instance.name} -> {ret}")
        return ret

    def __set__(self, instance: Any, value: Any) -> None:
        # This functions might be called by normal python functioning without using a parameter, 
        # when this happens instance is None and can crash the logging. 
        if instance is not None:
            setter = self.fset
            if setter:
                hints = get_type_hints(setter)
                expected_type = hints.get('value')
                if expected_type and not isinstance(value, expected_type):
                    msg = f"Expected {expected_type} but got {type(value)}"
                    raise TypeError(msg)
            
            logger.info(f"Setting {self.fget.__name__} in {instance.name} to {value}")

        super().__set__(instance, value)


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


# TODO: We should log when operations begin and end.
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

        # Call the available implementation of `setup`
        self.setup(specs)

    @property
    def params(self) -> list[str]:
        names = []
        for member in inspect.getmembers(self.__class__):
            if isinstance(member[1], Parameter):
                names.append(member[0])
        return names

    def info(self, attr: str, **kwargs) -> dict:
        DeviceInfo(name=self.name, desc=self.desc, dtype=self.dtype, status=self.status)

    @abstractmethod
    def setup(self, specs: dict) -> None:
        pass

    @abstractmethod
    def exec(self, seq: str, **kwargs) -> None | dict:
        pass

