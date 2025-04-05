# University of Illinois Urbana-Champaign
# Public Quantum Network
#
# NCSA/Illinois Computes

import logging
from collections.abc import Callable
from dataclasses import dataclass
from dataclasses import field
from functools import wraps
from typing import Any
from typing import Protocol
from typing import runtime_checkable

from pqnstack.base.errors import DeviceNotStartedError

logger = logging.getLogger(__name__)


@runtime_checkable
@dataclass(slots=True)
class Driver(Protocol):
    address: str = ""
    _device: Any = field(init=False, default=None)

    def start(self) -> None: ...
    def close(self) -> None: ...

    @property
    def status(self) -> dict[str, Any]:
        if not hasattr(self._device, "status") or self._device.status is None:
            return {}

        return self._device.status if self._device.status else {}


def require_started[T](driver_method: Callable[..., T]) -> Callable[..., T]:
    @wraps(driver_method)
    def wrapper(self: Driver, *args: Any, **kwargs: Any) -> T:
        if self._device is None:
            msg = "Device is not started"
            raise DeviceNotStartedError(msg)
        return driver_method(self, *args, **kwargs)

    return wrapper
