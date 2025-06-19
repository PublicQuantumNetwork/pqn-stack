import logging
from dataclasses import dataclass
from dataclasses import field
from typing import cast

from pqnstack.base.instrument import Instrument
from pqnstack.base.instrument import InstrumentInfo
from pqnstack.base.instrument import log_operation
from pqnstack.network.client import Client
from pqnstack.pqn.drivers.rotator import RotatorInstrument
from pqnstack.pqn.drivers.timetagger import TimeTaggerInstrument
from pqnstack.pqn.protocols.chsh import Devices
from pqnstack.pqn.protocols.chsh import measure_chsh
from pqnstack.pqn.protocols.measurement import CHSHValue
from pqnstack.pqn.protocols.measurement import MeasurementConfig

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class CHSHInfo(InstrumentInfo):
    queue_length: int = 0


@dataclass(slots=True)
class CHSHDevice(Instrument):
    motor_config: dict[str, dict[str, str]] = field(default_factory=dict)
    tagger_config: dict[str, str] = field(default_factory=dict)
    queue_length: int = field(default=0)

    _motors: dict[str, RotatorInstrument] = field(init=False, repr=False)
    _tagger: TimeTaggerInstrument = field(init=False, repr=False)
    _client: Client = field(init=False, repr=False)

    _players: dict[str, bool] = field(default_factory=dict, init=False, repr=False)
    _submissions: dict[str, bool] = field(default_factory=dict, init=False, repr=False)
    _value_gathered: dict[str, bool] = field(default_factory=dict, init=False, repr=False)
    _value: int = field(default=0, init=False, repr=False)

    def __post_init__(self) -> None:
        self._client = Client(host="172.30.63.109", timeout=600000)
        self._motors: dict[str, RotatorInstrument] = {
            motor: cast("RotatorInstrument", self._client.get_device(values["location"], values["name"]))
            for motor, values in self.motor_config.items()
        }
        self._tagger: TimeTaggerInstrument = cast(
            "TimeTaggerInstrument", self._client.get_device(self.tagger_config["location"], self.tagger_config["name"])
        )
        self.operations["measure_chsh"] = self.measure_chsh

    def start(self) -> None:
        logger.info("CHSHDevice started.")

    def close(self) -> None:
        logger.info("CHSHDevice closed.")

    @property
    def info(self) -> CHSHInfo:
        return CHSHInfo(
            name=self.name,
            desc=self.desc,
            hw_address=self.hw_address,
            queue_length=self.queue_length,
        )

    @log_operation
    def measure_chsh(self, basis1: list[float], basis2: list[float], config: MeasurementConfig) -> CHSHValue:
        self.queue_length += 1
        devices = Devices(
            idler_hwp=self._motors["idler_hwp"],
            idler_qwp=self._motors.get("idler_qwp"),
            signal_hwp=self._motors["signal_hwp"],
            signal_qwp=self._motors.get("signal_qwp"),
            timetagger=self._tagger,
        )

        self.queue_length -= 1

        return measure_chsh(
            basis1=basis1,
            basis2=basis2,
            devices=devices,
            config=config,
        )
