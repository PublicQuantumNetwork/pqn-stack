import logging
from dataclasses import dataclass
from dataclasses import field

from pydantic import BaseModel

from pqnstack.constants import BellState
from pqnstack.constants import QKDEncodingBasis
from pqnstack.pqn.protocols.measurement import MeasurementConfig

logger = logging.getLogger(__name__)


@dataclass
class CHSHSettings:
    # Specifies which half waveplate to use for the CHSH experiment. First value is the provider's name, second is the motor name.
    hwp: tuple[str, str] = ("", "")
    request_hwp: tuple[str, str] = ("", "")
    measurement_config: MeasurementConfig = field(default_factory=lambda: MeasurementConfig(5))


@dataclass
class QKDSettings:
    hwp: tuple[str, str] = ("", "")
    request_hwp: tuple[str, str] = ("", "")
    bitstring_length: int = 4
    discriminating_threshold = 10
    measurement_config: MeasurementConfig = field(default_factory=lambda: MeasurementConfig(5))


@dataclass
class Settings:
    router_name: str
    router_address: str
    router_port: int
    chsh_settings: CHSHSettings
    qkd_settings: QKDSettings
    bell_state: BellState = BellState.Phi_plus
    timetagger: tuple[str, str] | None = None  # Name of the timetagger to use for the CHSH experiment.


static_typecheck_msg = "Please set the global 'settings' variable before use."


def get_settings() -> Settings:
    raise NotImplementedError(static_typecheck_msg)


settings = get_settings()


class NodeState(BaseModel):
    chsh_request_basis: list[float] = [22.5, 67.5]
    # FIXME: Use enums for this
    qkd_basis_list: list[QKDEncodingBasis] = [
        QKDEncodingBasis.DA,
        QKDEncodingBasis.DA,
        QKDEncodingBasis.DA,
        QKDEncodingBasis.DA,
        QKDEncodingBasis.DA,
        QKDEncodingBasis.DA,
        QKDEncodingBasis.HV,
        QKDEncodingBasis.HV,
        QKDEncodingBasis.HV,
        QKDEncodingBasis.HV,
        QKDEncodingBasis.HV,
    ]
    qkd_bit_list: list[int] = []
    qkd_resulting_bit_list: list[int] = []  # Resulting bits after QKD
    qkd_request_basis_list: list[QKDEncodingBasis] = []  # Basis angles for QKD
    qkd_request_bit_list: list[int] = []


state = NodeState()
