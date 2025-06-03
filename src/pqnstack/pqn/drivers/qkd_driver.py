from dataclasses import dataclass
from typing import TYPE_CHECKING
from typing import cast

from pqnstack.base.driver import DeviceClass
from pqnstack.base.driver import DeviceDriver
from pqnstack.base.driver import DeviceInfo
from pqnstack.base.driver import log_operation
from pqnstack.base.errors import DeviceNotStartedError
from pqnstack.network.client import Client

if TYPE_CHECKING:
    from pqnstack.pqn.drivers.timetagger import TimeTaggerDevice


@dataclass
class QKDInfo(DeviceInfo):
    number_trials: int
    trial_values: list[float]


class QKDDevice(DeviceDriver):
    DEVICE_CLASS = DeviceClass.MANAGER

    def __init__(
        self,
        address: str,
        motors: dict[str, dict[str, str]],
        tagger_config: dict[str, str],
        name: str = "QKD Device",
        desc: str = "Device used for managing QKD Protocol",
    ) -> None:
        super().__init__(name=name, desc=desc, address=address)
        self._client: Client = Client(host="172.30.63.109", timeout=30000)
        self._tagger_config: dict[str, str] = tagger_config
        self._tagger: TimeTaggerDevice
        self._motors: dict[str, dict[str, str]] = motors
        self._players: dict[str, bool] = {"player1": False, "player2": False}
        self._submissions: dict[str, bool] = {"player1": False, "player2": False}
        self._value_gathered: dict[str, bool] = {"player1": False, "player2": False}
        self._value: int | None = None

        self.operations["add_player"] = self.add_player
        self.operations["remove_player"] = self.remove_player
        self.operations["get_motors"] = self.get_motors
        self.operations["submit"] = self.submit
        self.operations["get_counts"] = self.get_counts

    def start(self) -> None:
        self._set_tagger(self._tagger_config)

    def close(self) -> None:
        return

    def info(self) -> QKDInfo:
        return QKDInfo(
            name=self.name,
            desc=self.desc,
            address=self.address,
            dtype=self.DEVICE_CLASS,
            status=self.status,
            number_trials=0,
            trial_values=[],
        )

    @log_operation
    def _set_motors(self, **kwargs: dict[str, str]) -> None:
        self._motors.update(kwargs)

    @log_operation
    def _set_tagger(self, tagger: dict[str, str]) -> None:
        self._tagger = cast("TimeTaggerDevice", self._client.get_device(tagger["location"], tagger["name"]))

    @log_operation
    def add_player(self) -> str:
        for player, active in self._players.items():
            if not active:
                self._players[player] = True
                return player
        return ""

    @log_operation
    def remove_player(self, player: str) -> None:
        if player in self._players:
            self._players[player] = False

    @log_operation
    def get_motors(self, player: str) -> dict[str, dict[str, str]]:
        if player not in self._players:
            return {}
        key_filter = "signal" if player == "player1" else "idler"
        return {name: info for name, info in self._motors.items() if key_filter in name}

    @log_operation
    def submit(self, player: str) -> None:
        if player in self._submissions:
            self._submissions[player] = True

        if self._all_submitted():
            if self._tagger is None:
                msg = "TimeTagger is not set"
                raise DeviceNotStartedError(msg)
            self._value = self._tagger.measure_coincidence(1, 2, 500, int(5e12))

    def _all_submitted(self) -> bool:
        return all(self._submissions.values())

    def _all_measured(self) -> bool:
        return all(self._value_gathered.values())

    @log_operation
    def get_counts(self, player: str) -> int | None:
        counts: int | None = None
        if self._all_submitted():
            self._value_gathered[player] = True
            counts = self._value

        if self._all_measured():
            self._value = None
            for key in self._submissions:
                self._submissions[key] = False
                self._value_gathered[key] = False

        return counts
