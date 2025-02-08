from pqnstack.base.driver import DeviceClass
from pqnstack.base.driver import DeviceDriver
from pqnstack.base.driver import DeviceInfo
from pqnstack.base.driver import DeviceStatus
from pqnstack.base.driver import log_operation
from pqnstack.base.driver import log_parameter
from pqnstack.base.errors import DeviceNotStartedError

from time import sleep

logger = logging.getLogger(__name__)

@dataclass
class QKDInfo(DeviceInfo):
    number_trials: float
    trial_values: list


class QKDDevice(DeviceDriver):
    DEVICE_CLASS = DeviceClass.PROTOCOL

    def __init__(self, address: str, name: str = "QKD Device", desc: str = "Device used for managing QKD Protocol") -> None:    
        super().__init__(name, desc, address)

        self.tagger = None
        self.motors = None
        self.player1, self.player2 = False, False
        self.player1_submission, self.player2_submisson = False, False
        self.player_values = {"player1": [], "player2": []} 

    @log_operation
    def set_motors(self, **kwargs) -> None:
        self.motors = kwargs

    @log_operation
    def set_tagger(self, tagger) -> None:
        self.tagger = tagger

    @log_operation
    def add_player(self) -> str:
        for player in ["player1", "player2"]:
            if not getattr(self, player):
                setattr(self, player, True)
                return player
        return ""

    @log_operation
    def remove_player(self, player: str) -> None:
        setattr(self, player, False)

    @log_operation
    def get_motors(self, player: str) -> dict:
        if player == "player1":
            return {k: v for k, v in self.motors.items() if "signal" in k}
        elif player == "player2":
            return {k: v for k, v in self.motors.items() if "idler" in k}
        else:
            return {}

    @log_operation
    def get_tagger(self) -> None:
        return self.tagger

    @log_operation
    def submit(self, player: str) -> None:
        setattr(self, f"{player}_submission", True)
        
    @log_operation
    def check_submission(self):
        return all(getattr(self, f"player{i}_submission") for i in (1, 2))

    @log_operation
    def measured(self, player: str) -> None:
        setattr(self, f"{player}_submission", False)

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
  
def qkd_run(qkd_device: QKDDevice, basis: list, player: str = None, finished: bool = False) -> str, bool:
    """basis is in the form [(hwp value, qwp value)] or [hwp value]"""
    if player = None:
        player = qkd_device.add_player()

    motors = qkd_device.get_motors(player)

    qkd_device.submit(player)

    while(qkd_device.check_submission()):
        sleep(0.5)
        
    for k, v in motors.items():
        if "signal" in k:
            v.move_to(basis[])
