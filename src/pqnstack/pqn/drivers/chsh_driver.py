import logging
import threading
import queue
import time

from dataclasses import dataclass
from typing import Any, Dict, Optional


from pqnstack.base.driver import DeviceClass, DeviceDriver, log_operation
from pqnstack.base.driver import DeviceInfo
from pqnstack.network.client import Client
from pqnstack.pqn.protocols.chsh import measure_chsh

logger = logging.getLogger(__name__)

@dataclass
class CHSHInfo(DeviceInfo):
    queue_length: int = 0

class CHSHDevice(DeviceDriver):
    DEVICE_CLASS = DeviceClass.MANAGER

    def __init__(self, address: str, motors: dict[str: dict[str: str]], tagger_config: dict[str, str], name: str = "CHSH Device", desc: str = "Device for managing CHSH requests"):
        super().__init__(name, desc, address)
        self.c = Client(host="172.30.63.109", timeout=30000)
        self.motors = {motor: self.c.get_device(values["location"], values["name"]) for motor, values in motors.items()}
        self.tagger = self.c.get_device(tagger_config["location"], tagger_config["name"])

        self.operations["measure_chsh"] = self.measure_chsh

    def start(self):
        logger.info("CHSHDevice started.")

    def close(self):
        logger.info("CHSHDevice closed.")

    def info(self):
        return CHSHInfo(queue_length=self._request_queue.qsize())

    @log_operation
    def measure_chsh(self,
                     basis1, basis2,
                     measurement_duration,
                     binwidth=500e-12,
                     channel1=1, channel2=2,
                     dark_count=0, **kwargs) -> Dict[str, Any]:

        result_holder = {"success": False, "value": None}

        done_event = threading.Event()
        
        request = {
            "kwargs": {
                "basis1": basis1,
                "basis2": basis2,
                "idler_hwp": self.motors["idler_hwp"],
                "idler_qwp": self.motors["idler_hwp"],
                "signal_hwp": self.motors["signal_hwp"],
                "signal_qwp": self.motors["signal_hwp"],
                "timetagger": self.tagger,
                "measurement_duration": measurement_duration,
                "binwidth": binwidth,
                "channel1": channel1,
                "channel2": channel2,
                "dark_count": dark_count
            },
            "done_event": done_event,
            "result_holder": result_holder
        }

        return measure_chsh(**request["kwargs"])
