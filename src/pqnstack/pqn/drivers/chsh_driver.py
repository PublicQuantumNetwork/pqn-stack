import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING
from typing import cast

from pqnstack.base.driver import DeviceClass
from pqnstack.base.driver import DeviceDriver
from pqnstack.base.driver import DeviceInfo
from pqnstack.base.driver import DeviceStatus
from pqnstack.base.driver import log_operation
from pqnstack.network.client import Client
from pqnstack.pqn.protocols.chsh import Devices
from pqnstack.pqn.protocols.chsh import measure_chsh
from pqnstack.pqn.protocols.measurement import CHSHValue
from pqnstack.pqn.protocols.measurement import MeasurementConfig

logger = logging.getLogger(__name__)


if TYPE_CHECKING:
    from pqnstack.pqn.drivers.rotator import RotatorDevice
    from pqnstack.pqn.drivers.timetagger import TimeTaggerDevice


@dataclass
class CHSHInfo(DeviceInfo):
    name: str
    desc: str
    address: str
    dtype: DeviceClass
    status: DeviceStatus
    queue_length: int


class CHSHDevice(DeviceDriver):
    DEVICE_CLASS = DeviceClass.MANAGER

    def __init__(
        self,
        address: str,
        motors: dict[str, dict[str, str]],
        tagger_config: dict[str, str],
        name: str = "CHSH Device",
        desc: str = "Device for managing CHSH requests",
    ) -> None:
        super().__init__(name, desc, address)
        self.address = address
        self.motor_config = motors
        self.tagger_config = tagger_config
        self.name = name
        self.desc = desc
        self.queue_length = 0
        self.c = Client(host="172.30.63.109", timeout=600000)
        self.motors: dict[str, RotatorDevice] = {
            motor: cast("RotatorDevice", self.c.get_device(values["location"], values["name"]))
            for motor, values in motors.items()
        }
        self.tagger: TimeTaggerDevice = cast(
            "TimeTaggerDevice", self.c.get_device(tagger_config["location"], tagger_config["name"])
        )
        self.operations["measure_chsh"] = self.measure_chsh

    def start(self) -> None:
        logger.info("CHSHDevice started.")

    def close(self) -> None:
        logger.info("CHSHDevice closed.")

    def info(self) -> CHSHInfo:
        return CHSHInfo(
            name=self.name,
            desc=self.desc,
            address=self.address,
            dtype=DeviceClass.MANAGER,
            status=DeviceStatus.READY,
            queue_length=self.queue_length,
        )

    @log_operation
    def measure_chsh(self, basis1: list[float], basis2: list[float], config: MeasurementConfig) -> CHSHValue:
        self.queue_length += 1
        devices = Devices(
            idler_hwp=self.motors["idler_hwp"],
            idler_qwp=self.motors.get("idler_qwp"),
            signal_hwp=self.motors["signal_hwp"],
            signal_qwp=self.motors.get("signal_qwp"),
            timetagger=self.tagger,
        )

        self.queue_length -= 1

        return measure_chsh(
            basis1=basis1,
            basis2=basis2,
            devices=devices,
            config=config,
        )
