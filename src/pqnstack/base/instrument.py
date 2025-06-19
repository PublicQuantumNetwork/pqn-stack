# University of Illinois Urbana-Champaign
# Public Quantum Network
#
# NCSA/Illinois Computes

import atexit
import datetime
import logging
from collections.abc import Callable
from dataclasses import dataclass
from dataclasses import field
from functools import wraps
from time import perf_counter
from typing import Any
from typing import Protocol
from typing import runtime_checkable

from pqnstack.base.errors import LogDecoratorOutsideOfClassError

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class InstrumentInfo:
    name: str = ""
    desc: str = ""
    hw_address: str = ""
    hw_status: dict[str, Any] = field(default_factory=dict)


@runtime_checkable
@dataclass(slots=True)
class Instrument(Protocol):
    """Base class for all instruments in the PQN stack.

    Some rules for instruments:

      * You cannot use the character `:` in the names of instruments. This is used to separate parts of requests in
        proxy instruments.

    """

    name: str
    desc: str
    hw_address: str
    parameters: set[str] = field(default_factory=set)
    operations: dict[str, Callable[..., Any]] = field(default_factory=dict)

    def __post_init__(self) -> None:
        atexit.register(self.close)

    def start(self) -> None: ...
    def close(self) -> None: ...

    @property
    def info(self) -> InstrumentInfo: ...


def log_operation[T](func: Callable[..., T]) -> Callable[..., T]:
    @wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> T:
        if len(args) == 0:
            msg = "log_operation has 0 args, this usually indicates that it has been used to decorate something that is not a class method. This is not allowed."
            raise LogDecoratorOutsideOfClassError(msg)

        ins = args[0]
        if not isinstance(ins, Instrument):
            msg = "log_operation has been used to decorate something that is not a Instrument method. This is not allowed."
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
        if not isinstance(ins, Instrument):
            msg = (
                "log_operation has been used to decorate something that is not a Instrument method. "
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
