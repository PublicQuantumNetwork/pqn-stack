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
from time import perf_counter
from typing import Any

from pqnstack.base.errors import LogDecoratorOutsideOfClassError

logger = logging.getLogger(__name__)


class DeviceClass(Enum):
    SENSOR = auto()
    MOTOR = auto()
    TEMPCTRL = auto()
    TIMETAGR = auto()
    PROXY = auto()
    TESTING = auto()
    MANAGER = auto()


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


class DeviceDriver(ABC):
    """
    Base class for all drivers in the PQN stack.

    Some rules for drivers:

      * You cannot use the character `:` in the names of instruments. This is used to separate parts of requests in
        proxy instruments.


    """

    DEVICE_CLASS: DeviceClass = DeviceClass.TESTING

    def __init__(self, name: str, desc: str, address: str) -> None:
        self.name = name
        self.desc = desc
        self.address = address

        self.status = DeviceStatus.OFF

        self.parameters: set[str] = set()
        # FIXME: operations is overloaded with the big operations of the system. We should make it mean single thing.
        self.operations: dict[str, Callable[[Any], Any]] = {}

        atexit.register(self.close)

    @abstractmethod
    def info(self) -> DeviceInfo: ...

    @abstractmethod
    def start(self) -> None: ...

    @abstractmethod
    def close(self) -> None: ...

    def __setattr__(self, key: str, value: Any) -> None:
        super().__setattr__(key, value)


def log_operation[T](func: Callable[..., T]) -> Callable[..., T]:
    @wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> T:
        if len(args) == 0:
            msg = "log_operation has 0 args, this usually indicates that it has been used to decorate something that is not a class method. This is not allowed."
            raise LogDecoratorOutsideOfClassError(msg)

        ins = args[0]
        if not isinstance(ins, DeviceDriver):
            msg = "log_operation has been used to decorate something that is not a DeviceDriver method. This is not allowed."
            raise LogDecoratorOutsideOfClassError(msg)

        start_time = perf_counter()
        logger.info(
            "%s| %s, %s |Starting operation '%s' with args: '%s' and kwargs '%s'",
            start_time,
            ins.name,
            type(ins),
            func.__name__,
            args,
            kwargs,
        )

        result = func(*args, **kwargs)

        end_time = perf_counter()
        duration = end_time - start_time
        logger.info(
            "%s | %s, %s | Completed operation %s. Duration: %s",
            end_time,
            ins.name,
            type(ins),
            func.__name__,
            duration,
        )

        return result

    return wrapper


def log_parameter[T](func: Callable[..., T]) -> Callable[..., T]:
    @wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> T:
        if len(args) == 0:
            msg = (
                "log_parameter has 0 args, "
                "this usually indicates that it has been used to decorate something that is not a class method. "
                "This is not allowed."
            )
            raise LogDecoratorOutsideOfClassError(msg)

        ins = args[0]
        if not isinstance(ins, DeviceDriver):
            msg = (
                "log_operation has been used to decorate something that is not a DeviceDriver method. "
                "This is not allowed."
            )
            raise LogDecoratorOutsideOfClassError(msg)

        # if no args or kwargs, we are reading the value of the param, else we are setting it.
        if len(args) == 1 and len(kwargs) == 0:
            current_time = datetime.datetime.now(tz=datetime.UTC)
            result = func(*args, **kwargs)
            logger.info(
                "%s | %s, %s | Parameter '%s' got read with value %s",
                current_time,
                ins.name,
                type(ins),
                func.__name__,
                result,
            )

        else:
            start_time = perf_counter()
            result = func(*args, **kwargs)  # Always return None
            end_time = perf_counter()
            duration = end_time - start_time
            logger.info(
                "%s | %s, %s | Parameter '%s' got updated to '%s', parameter update took %s long ",
                end_time,
                ins.name,
                type(ins),
                func.__name__,
                args[1:],
                duration,
            )

        return result

    return wrapper
