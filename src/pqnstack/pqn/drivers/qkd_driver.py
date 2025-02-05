from typing import List, Tuple

from pqnstack.base.driver import DeviceClass
from pqnstack.base.driver import DeviceDriver
from pqnstack.base.driver import DeviceInfo
from pqnstack.base.driver import DeviceStatus
from pqnstack.base.driver import log_operation
from pqnstack.base.driver import log_parameter
from pqnstack.base.errors import DeviceNotStartedError

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
        self.values = [] 

    @log_operation
    def set_motors(self, **kwargs) -> None:
        self.motors = kwargs

    @log_operation
    def set_tagger(self, tagger) -> None:
        self.tagger = tagger
    
    @log_operation
    def measure_pass(self, signal_basis: list, idler_basis: list) -> bool:
        """If basis is in the form [(hwp value, qwp value)], then self.motors need to include qwps, else should be in form [hwp value]"""

        has_qwp = all(k in self.motors for k in ["signal_qwp", "idler_qwp"])
        for basis_step in zip(signal_basis, idler_basis):
            for channel, pos in zip(["signal", "idler"], basis_step):
                for i, wp in enumerate(["hwp", "qwp"] if has_qwp else ["hwp"]):
                    self.motors[f"{channel}_{wp}"].move_to(pos[i] if has_qwp else pos)

            self.values.append()
            return(self.tagger.measure_coincidence())






    
