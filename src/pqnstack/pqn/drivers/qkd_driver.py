from pqnstack.base.driver import DeviceClass
from pqnstack.base.driver import DeviceDriver
from pqnstack.base.driver import DeviceInfo
from pqnstack.base.driver import DeviceStatus
from pqnstack.base.driver import log_operation
from pqnstack.base.driver import log_parameter
from pqnstack.base.errors import DeviceNotStartedError
from pqnstack.network.client import Client
import logging
from dataclasses import dataclass

from time import sleep

logger = logging.getLogger(__name__)

@dataclass
class QKDInfo(DeviceInfo):
    number_trials: float
    trial_values: list


class QKDDevice(DeviceDriver):
    DEVICE_CLASS = DeviceClass.PROTOCOL

    def __init__(self, address: str, motors: dict[str: dict[str: str]], tagger_config: dict[str, str], name: str = "QKD Device", desc: str = "Device used for managing QKD Protocol") -> None:    
        super().__init__(name, desc, address)
        self.c = Client(host="172.30.63.109", timeout=30000)
        self.tagger_config = tagger_config
        self.tagger = {}
        self.motors = motors
        self.players = {"player1": False, "player2": False}
        self.submissions = {"player1": False, "player2": False}
        self.value_gathered = {"player1": False, "player2": False}
        self.value: int = None
        self.operations["add_player"] = self.add_player
        self.operations["submit"] = self.submit
        self.operations["get_counts"] = self.get_counts
        self.operations["get_motors"] = self.get_motors
        self.operations["remove_player"] = self.remove_player

    def start(self):
        self._set_tagger(self.tagger_config)
        return

    def close(self):
        return

    def info(self):
        return QKDInfo(number_trials = 0, trial_values = [0])

    @log_operation
    def _set_motors(self, **kwargs) -> None:
        self.motors.update(kwargs)

    @log_operation
    def _set_tagger(self, tagger: dict) -> None:
        self.tagger = self.c.get_device(tagger["location"], tagger["name"])

    @log_operation
    def add_player(self) -> str:
        for player, active in self.players.items():
            if not active:
                self.players[player] = True
                return player
        return ""

    @log_operation
    def remove_player(self, player: str) -> None:
        if player in self.players:
            self.players[player] = False

    @log_operation
    def get_motors(self, player: str) -> dict:
        if player in self.players:
            key_filter = "signal" if player == "player1" else "idler"
            return {k: v for k, v in self.motors.items() if key_filter in k}
        return {}

    @log_operation
    def submit(self, player: str) -> None:
        if player in self.submissions:
            self.submissions[player] = True

        if self._check_submission():
            self.value = self.tagger.measure_coincidence(1, 2, 500, int(5e12))
            
    @log_operation
    def _measured(self, player: str) -> None:
        if player in self.value_gathered:
            self.value_gathered[player] = True

    def _check_submission(self) -> bool:
        return all(self.submissions.values())

    def _check_measured(self) -> bool:
        return all(self.value_gathered.values())

    @log_operation
    def get_counts(self, player: str) -> int:
        counts = None
        if self._check_submission():
            self._measured(player)
            counts = self.value
        if self._check_measured():
            self.value = None
            self.submissions["player1"] = False
            self.submissions["player2"] = False
            self.value_gathered["player1"] = False
            self.value_gathered["player2"] = False
       
        return counts

    @log_operation
    def measure_pass(self, player: str, signal_basis: list, idler_basis: list) -> bool:
        """If basis is in the form [(hwp value, qwp value)], then self.motors need to include qwps, else should be in form [hwp value]"""

        has_qwp = all(k in self.motors for k in ["signal_qwp", "idler_qwp"])
        for basis_step in zip(signal_basis, idler_basis):
            for channel, pos in zip(["signal", "idler"], basis_step):
                for i, wp in enumerate(["hwp", "qwp"] if has_qwp else ["hwp"]):
                    self.motors[f"{channel}_{wp}"].move_to(pos[i] if has_qwp else pos)

            self.values.append()
            return(self.tagger.measure_coincidence())
