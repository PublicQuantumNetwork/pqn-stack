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
from dataclasses import field
from enum import StrEnum
from enum import auto
from functools import wraps
from time import perf_counter
from typing import Any

from pqnstack.base.driver import Driver
from pqnstack.base.errors import LogDecoratorOutsideOfClassError

logger = logging.getLogger(__name__)


class InstrumentClass(StrEnum):
    SENSOR = auto()
    MOTOR = auto()
    TEMPCTRL = auto()
    TIMETAGGER = auto()
    PROXY = auto()
    TESTING = auto()


class InstrumentStatus(StrEnum):
    OFF = auto()
    READY = auto()
    BUSY = auto()
    FAIL = auto()


@dataclass(frozen=True, slots=True)
class InstrumentInfo:
    dtype: InstrumentClass = field(default=InstrumentClass.TESTING)
    status: InstrumentStatus = field(default=InstrumentStatus.OFF)
    address: str = ""
    hardware_status: dict[str, Any] = field(default_factory=dict)


class NetworkInstrument[GenericDriver: Driver](ABC):
    """Base class for all instruments in the PQN stack.

    Some rules for instruments:

      * You cannot use the character `:` in the names of instruments. This is used to separate parts of requests in
        proxy instruments.
    """

    INSTRUMENT_CLASS: InstrumentClass = InstrumentClass.TESTING

    def __init__(self, name: str, desc: str, driver: GenericDriver) -> None:
        self.name = name
        self.desc = desc
        self.driver = driver

        self.status = InstrumentStatus.OFF

        self.parameters: set[str] = set()
        # FIXME: operations is overloaded with the big operations of the system. We should make it mean single thing.
        self.operations: dict[str, Callable[[Any], Any]] = {}

        atexit.register(self.close)

    @property
    @abstractmethod
    def info(self) -> InstrumentInfo:
        return InstrumentInfo(self.INSTRUMENT_CLASS, self.status)

    @abstractmethod
    def start(self) -> None:
        self.driver.start()
        self.status = InstrumentStatus.READY

    @abstractmethod
    def close(self) -> None:
        self.driver.close()
        self.status = InstrumentStatus.OFF

    # TODO: Why is this here?
    def __setattr__(self, key: str, value: Any) -> None:
        super().__setattr__(key, value)


def log_operation[T](func: Callable[..., T]) -> Callable[..., T]:
    @wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> T:
        if len(args) == 0:
            msg = "log_operation has 0 args, this usually indicates that it has been used to decorate something that is not a class method. This is not allowed."
            raise LogDecoratorOutsideOfClassError(msg)

        ins = args[0]
        if not isinstance(ins, NetworkInstrument):
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
        if not isinstance(ins, NetworkInstrument):
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
