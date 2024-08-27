# University of Illinois Urbana-Champaign
# Public Quantum Network
#
# NCSA/Illinois Computes

from abc import ABC, abstractmethod
from typing import Dict
from enum import Enum


class DeviceDriver(ABC):

    def __init__(self, specs: Dict):
        # Self-documenting features
        self.name = specs['name']
        self.desc = specs['desc']
        self.dtype = DeviceClass[specs['dtype']]
        self.status = DeviceStatus.NOINIT

        # Executable functionalities
        self.provides = specs['provides']
        self.executable = {}

        # Tunable device parameters across multiple experiments
        self.params = specs['params']

        # Call the available implementation of `setup`
        self.setup(specs)

    def info(self, attr: str, **kwargs):
        return {
            'name': self.name,
            'desc': self.desc,
            'dtype': self.dtype.value,
            'status': self.status.value
        }

    @abstractmethod
    def setup(self, specs: Dict):
        pass

    @abstractmethod
    def exec(self, seq: str, **kwargs) -> Dict:
        pass


class DeviceClass(Enum):
    SENSOR = 1
    MOTOR = 2
    TEMPCTRL = 3
    TIMETAGR = 4


class DeviceStatus(Enum):
    NOINIT = 'not uninitialized'
    FAIL = 'fail'
    OFF = 'off'
    IDLE = 'idle'
    ON = 'on'
