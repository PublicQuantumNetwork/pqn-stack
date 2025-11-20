from dataclasses import dataclass
from dataclasses import field
from typing import cast

from pqnstack.base.errors import DeviceNotStartedError
from pqnstack.base.instrument import Instrument
from pqnstack.base.instrument import InstrumentInfo
from pqnstack.base.instrument import TimeTaggerInstrument
from pqnstack.base.instrument import log_operation
from pqnstack.network.client import Client


@dataclass(frozen=True, slots=True)
class QKDInfo(InstrumentInfo):
    number_trials: int = 0
    trial_values: list[float] = field(default_factory=list)


@dataclass(slots=True)
class QKDDevice(Instrument):
    motor_config: dict[str, dict[str, str]] = field(default_factory=dict)
    tagger_config: dict[str, str] = field(default_factory=dict)

    _tagger: TimeTaggerInstrument = field(init=False, repr=False)
    _client: Client = field(init=False, repr=False)

    _players: dict[str, bool] = field(default_factory=dict, init=False, repr=False)
    _submissions: dict[str, bool] = field(default_factory=dict, init=False, repr=False)
    _value_gathered: dict[str, bool] = field(default_factory=dict, init=False, repr=False)
    _value: int = 0

    def __post_init__(self) -> None:
        self._client = Client(host="172.30.63.109", timeout=30000)

        self._players: dict[str, bool] = {"player1": False, "player2": False}
        self._submissions: dict[str, bool] = {"player1": False, "player2": False}
        self._value_gathered: dict[str, bool] = {"player1": False, "player2": False}

        self.operations["add_player"] = self.add_player
        self.operations["remove_player"] = self.remove_player
        self.operations["get_motors"] = self.get_motors
        self.operations["submit"] = self.submit
        self.operations["get_counts"] = self.get_counts

    def start(self) -> None:
        self._set_tagger(self.tagger_config)

    def close(self) -> None:
        return

    @property
    def info(self) -> QKDInfo:
        return QKDInfo(
            name=self.name,
            desc=self.desc,
            hw_address=self.hw_address,
            number_trials=0,
            trial_values=[],
        )

    @log_operation
    def _set_motors(self, **kwargs: dict[str, str]) -> None:
        self.motor_config.update(kwargs)

    @log_operation
    def _set_tagger(self, tagger: dict[str, str]) -> None:
        self._tagger = cast("TimeTaggerInstrument", self._client.get_device(tagger["location"], tagger["name"]))

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
        return {name: info for name, info in self.motor_config.items() if key_filter in name}

    @log_operation
    def submit(self, player: str) -> None:
        if player in self._submissions:
            self._submissions[player] = True

        if self._all_submitted():
            if self._tagger is None:
                msg = "TimeTagger is not set"
                raise DeviceNotStartedError(msg)
            self._value = self._tagger.measure_correlation(1, 2, integration_time_s=5, binwidth_ps=5)

    def _all_submitted(self) -> bool:
        return all(self._submissions.values())

    def _all_measured(self) -> bool:
        return all(self._value_gathered.values())

    @log_operation
    def get_counts(self, player: str) -> int:
        counts = -1

        if self._all_submitted():
            self._value_gathered[player] = True
            counts = self._value

        if self._all_measured():
            self._value = 0
            for key in self._submissions:
                self._submissions[key] = False
                self._value_gathered[key] = False

        return counts
