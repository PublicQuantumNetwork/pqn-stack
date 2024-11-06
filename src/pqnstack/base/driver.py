# University of Illinois Urbana-Champaign
# Public Quantum Network
#
# NCSA/Illinois Computes

import atexit
import datetime
import logging
from abc import ABC
from abc import abstractmethod
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from enum import StrEnum
from enum import auto
from functools import wraps

from pqnstack.base.errors import LogDecoratorOutsideOfClassError

logger = logging.getLogger(__name__)


class DeviceClass(Enum):
    SENSOR = auto()
    MOTOR = auto()
    TEMPCTRL = auto()
    TIMETAGR = auto()
    TESTING = auto()


class DeviceStatus(StrEnum):
    OFF = auto()
    READY = auto()
    BUSY = auto()
    FAIL = auto()


@dataclass
class DeviceInfo:
    name: str
    desc: str
    address: str  # Whatever unique identifier is used to communicate with the device.
    dtype: DeviceClass
    status: DeviceStatus


# TODO: Does this guy know about the class that this thing is being wrapped from? If not it might be worth making it.
def log_operation(func):
    """
    Decorator for logging parameters and function calls.
    Inspired from: https://ankitbko.github.io/blog/2021/04/logging-in-python/

    :param func:
    :return:
    """
    @wraps(func)
    def wrapper(*args, **kwargs):

        if len(args) < 0:
            msg = ("log_operation has 0 args, "
                   "this usually indicates that it has been used to decorate something that is not a class method. "
                   "This is not allowed.")
            raise LogDecoratorOutsideOfClassError(msg)
        ins = args[0]

        start_time = datetime.datetime.now()
        logger.info("%s| %s, %s |Starting operation '%s' with args: '%s' and kwargs '%s'", start_time,
                    ins.name, type(ins), func.__name__, args, kwargs)

        result = func(*args, **kwargs)

        end_time = datetime.datetime.now()
        duration = end_time - start_time
        logger.info("%s | %s, %s | Completed operation %s. Duration: %s", end_time,
                    ins.name, type(ins), func.__name__, duration)

        return result

    return wrapper


def log_parameter(func):
    """
    Decorator for logging parameters and function calls.
    Inspired from: https://ankitbko.github.io/blog/2021/04/logging-in-python/

    :param func:
    :return:
    """
    @wraps(func)
    def wrapper(*args, **kwargs):

        if len(args) <= 0:
            msg = ("log_parameter has 0 args, "
                   "this usually indicates that it has been used to decorate something that is not a class method. "
                   "This is not allowed.")
            raise LogDecoratorOutsideOfClassError(msg)

        ins = args[0]

        # if no args or kwargs, we are reading the value of the param, else we are setting it.
        if len(args) == 1 and len(kwargs) == 0:
            current_time = datetime.datetime.now()
            result = func(*args, **kwargs)
            logger.info("%s | %s, %s | Parameter '%s' got read with value %s", current_time, ins.name, type(ins),
                        func.__name__, result)

        else:
            start_time = datetime.datetime.now()
            result = func(*args, **kwargs)
            end_time = datetime.datetime.now()
            duration = end_time - start_time
            logger.info("%s | %s, %s | Parameter '%s' got updated to '%s', parameter update took %s long ",
                        end_time, ins.name, type(ins), func.__name__, result, duration)

        return result

    return wrapper


class DeviceDriver(ABC):

    DEVICE_CLASS: DeviceClass = DeviceClass.TESTING

    def __init__(self, name: str, desc: str, address: str) -> None:
        self.name = name
        self.desc = desc
        self.address = address

        self.status = DeviceStatus.OFF

        self.parameters: dict[str, property] = {}
        # FIXME: operations is overloaded with the big operations of the system. We should make it mean single thing.
        self.operations: dict[str, Callable] = {}

        atexit.register(self.close)

    @abstractmethod
    def info(self) -> DeviceInfo: ...

    @abstractmethod
    def start(self) -> None: ...

    @abstractmethod
    def close(self) -> None: ...
