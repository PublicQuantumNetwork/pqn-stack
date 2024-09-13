# University of Illinois Urbana-Champaign
# Public Quantum Network
#
# NCSA/Illinois Computes

import logging
import inspect
import datetime
from abc import ABC
from typing import Any
from abc import abstractmethod
from dataclasses import dataclass
from collections.abc import Callable
from functools import wraps
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


class Operation:
    """
    Wrapper for operation methods in DeviceDriver.
    Classifies a function as an official Operation of the driver and adds loggin automatically.


    ```
    class MyDriver(DeviceDriver):
        ...

        @Operation
        def measure_x(self) -> int:
            return self.ask("measure_x")
    ```
    """
    def __init__(self, func):
        self.func = func
        wraps(func)(self)

    def __call__(self, *args, **kwargs):

        instance = self.func.__self__

        start_time = datetime.datetime.now()
        logger.info(f"Starting operation '{self.func.__name__}' on {instance.name} with args and kwargs {args, kwargs} "
                    f"| Time {start_time}")

        result = self.func(*args, **kwargs)

        end_time = datetime.datetime.now()
        duration = end_time - start_time
        logger.info(f"Completed operation '{self.func.__name__}' on {instance.name}. Duration: {duration}")

        return result

    def __get__(self, obj, objtype=None):
        if obj is None:
            return self
        # This line is necessary to have the function be a bound method instead of just a method.
        return self.__class__(self.func.__get__(obj, objtype))


class InvalidDriverError(Exception):
    """Not in errors file because DeviceDriver needs it and it leads to infinite imports."""
    def __init__(self, message: str = "") -> None:
        self.message = message
        super().__init__(self.message)


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


# TODO: Add communication abstraction layer and how does that look?
class DeviceDriver(ABC):
    """
    Drivers can have 4 types of members (python members, this includes class variables):
        1. ALLOWED_MEMBERS:
        2. Parameter objects. Functions that are decorated with @Parameter.
        3. Operation objects. Functions that are decorated with @Operation.
        4. Private members. These are internal functions that are not exposed to the user. 
        
    If the child driver does not follow these rules, the driver will raise an exception at initialization not letting the user use the driver.
    """

    # FIXME: This is a placeholder. We should generate this automatically from this specific class.
    ALLOWED_MEMBERS = ["name", "desc", "status", "info", "setup", "exec", "close", "params", "dtype", "operations", "ALLOWED_MEMBERS"]

    def __init__(self, specs: dict) -> None:
        # Self-documenting features
        self.name = specs["name"]
        self.desc = specs["desc"]

        self.status = DeviceStatus.NOINIT

        # FIXME: Clean this up
        # Executable functionalities
        # self.provides = specs["provides"]
        # self.executable: dict[str, Callable] = {}

        # Call the available implementation of `setup`
        self.setup(specs)

        # Validates class implementation
        self._validate_class()

    def _validate_class(self):
        # Checks that the implemented clas classifies itself
        if not isinstance(self.dtype, DeviceClass):
            # Checking for common case where the @property decorator is missing.
            if isinstance(self.dtype, Callable):
                msg = "It seems that you forgot the @property decorator when defining dtype."
                raise InvalidDriverError(msg)
            msg = f"dtype needs to return a DeviceClass instance not {type(self.dtype)}"
            raise InvalidDriverError(msg)

        # __class__ members checks for the members of the class istelf, leaving the Parameter and Operation type for
        # objects but leaving instance variables (any variable declared in the __init__) out. We can check if an
        # instance member is in the class member to see if they are Parameter or Operations
        class_members = {name: member for name, member in inspect.getmembers(self.__class__)}
        instance_members = {name: member for name, member in inspect.getmembers(self)}

        for name, member in instance_members.items():
            # Checks for built-in members
            if not (name.startswith("__") and name.endswith("__")):
                # Checks if member is private
                if not name.startswith("_") or name.startswith("__"):
                    # Checks if member is allowed
                    if name not in self.ALLOWED_MEMBERS:
                        if name in class_members:
                            # Checks if member is a Parameter or Operation
                            class_member = class_members[name]
                            if not isinstance(class_member, (Parameter, Operation)):
                                msg = f'Invalid member "{name}", read docstring of DeviceDriver for the rules.'
                                raise InvalidDriverError(msg)
                        else:
                            msg = f'Invalid member "{name}", read docstring of DeviceDriver for the rules.'
                            raise InvalidDriverError(msg)

    @property
    def params(self) -> list[str]:
        names = []
        for member in inspect.getmembers(self.__class__):
            if isinstance(member[1], Parameter):
                names.append(member[0])
        return names
    
    @property
    def operations(self) -> list[str]:
        operations = []
        for member in inspect.getmembers(self.__class__):
            if isinstance(member[1], Operation):
                operations.append(member[0])
        return operations

    @property
    @abstractmethod
    def dtype(self) -> DeviceClass:
        pass

    def info(self, attr: str, **kwargs) -> dict:
        DeviceInfo(name=self.name, desc=self.desc, dtype=self.dtype, status=self.status)

    @abstractmethod
    def setup(self, specs: dict) -> None:
        pass

    @abstractmethod
    def exec(self, seq: str, **kwargs) -> None | dict:
        pass

    @abstractmethod
    def close(self, **kwargs: Any) -> None:
        pass
