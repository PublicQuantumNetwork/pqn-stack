import logging
import time
from abc import abstractmethod
from dataclasses import dataclass

import zmq

from pqnstack.base.driver import DeviceClass
from pqnstack.base.driver import DeviceDriver
from pqnstack.base.driver import DeviceInfo
from pqnstack.base.driver import DeviceStatus
from pqnstack.base.driver import log_operation
from pqnstack.base.driver import log_parameter
from pqnstack.base.errors import DeviceNotStartedError

logger = logging.getLogger(__name__)


@dataclass
class TimetaggerInfo(DeviceInfo):
    ...

class Timetagger(DeviceDriver):
    
    DEVICE_CLASS = DeviceClass.TIMETAGR

    def __init__(self, name: str, desc: str, address: str, *arg, **kwargs) -> None:
        super().__init__(name, desc, address)

        self.operations["get_counts"] = self.get_counts
        self.operations["set_delay"] = self.set_delay
        self.operations["set_interval"] = self.set_interval

    @log_operation
    def get_counts(self, channels) -> float
        """Returns how many counts were detected in the set time window for any given channels """
        ...

    def 


