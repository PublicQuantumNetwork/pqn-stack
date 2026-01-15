import asyncio
import logging
from functools import lru_cache

from pydantic import BaseModel
from pydantic import Field
from pydantic_settings import BaseSettings
from pydantic_settings import PydanticBaseSettingsSource
from pydantic_settings import SettingsConfigDict
from pydantic_settings import TomlConfigSettingsSource

from pqnstack.constants import BellState
from pqnstack.constants import QKDEncodingBasis
from pqnstack.pqn.drivers.rotaryencoder import RotaryEncoderInstrument
from pqnstack.pqn.protocols.measurement import MeasurementConfig

logger = logging.getLogger(__name__)


class CHSHSettings(BaseModel):
    # Specifies which half waveplate to use for the CHSH experiment. First value is the provider's name, second is the motor name.
    hwp: tuple[str, str] = ("", "")
    request_hwp: tuple[str, str] = ("", "")
    measurement_config: MeasurementConfig = Field(default_factory=lambda: MeasurementConfig(integration_time_s=5))
    expectation_signs: tuple[int, int, int, int] = (1, 1, 1, -1)


class QKDSettings(BaseModel):
    hwp: tuple[str, str] = ("", "")
    request_hwp: tuple[str, str] = ("", "")
    bitstring_length: int = 6
    minimum_question_index: int = 1
    maximum_question_index: int = 8
    discriminating_threshold: int = 10
    measurement_config: MeasurementConfig = Field(default_factory=lambda: MeasurementConfig(integration_time_s=5))


class Settings(BaseSettings):
    node_name: str = "node1"
    router_name: str = "router1"
    router_address: str = "localhost"
    router_port: int = 5555
    chsh_settings: CHSHSettings = CHSHSettings()
    qkd_settings: QKDSettings = QKDSettings()
    bell_state: BellState = BellState.Phi_plus
    timetagger: tuple[str, str] | None = None  # Name of the timetagger to use for the CHSH experiment.
    rotary_encoder_address: str = "/dev/ttyACM0"
    virtual_rotator: bool = False  # If True, use terminal input instead of hardware rotary encoder

    rotary_encoder: RotaryEncoderInstrument | None = None

    model_config = SettingsConfigDict(toml_file="./config.toml", env_file=".env", env_file_encoding="utf-8")

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        return (
            TomlConfigSettingsSource(settings_cls),
            env_settings,
            dotenv_settings,
            file_secret_settings,
            init_settings,
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()


class NodeState(BaseModel):
    # Coordination state
    # FIXME: Make sure we are checking for the client_listening_for_follower_requests state everywhere.
    client_listening_for_follower_requests: bool = False

    # Leader's state
    leading: bool = False
    followers_address: str = ""

    # Follower's state
    following: bool = False
    # Other node requested this node to follow it.
    following_requested: bool = False
    # User's response to the follow request. None if no response yet, True if accepted, False if rejected.
    following_requested_user_response: bool | None = None
    # The address of the leader this node is following. None if not following anyone.
    leaders_address: str = ""
    leaders_name: str = ""

    # CHSH state
    chsh_request_basis: list[float] = [22.5, 67.5]

    # QKD state
    # FIXME: At the moment the reset_coordination_state resets this, probably want to refactor that function out.
    qkd_question_order: list[int] = []  # Order of questions for QKD
    qkd_emoji_pick: str = ""  # Emoji chosen for QKD
    qkd_leader_basis_list: list[QKDEncodingBasis] = [
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
    qkd_follower_basis_list: list[QKDEncodingBasis] = []
    qkd_single_bit_current_index: int = 0  # Current index in follower basis list for single_bit endpoint
    qkd_bit_list: list[int] = []
    qkd_resulting_bit_list: list[int] = []  # Resulting bits after QKD
    qkd_request_basis_list: list[QKDEncodingBasis] = []  # Basis angles for QKD
    qkd_request_bit_list: list[int] = []
    qkd_n_matching_bits: int = -1  # Leaders populate this value after qkd is done. Same with the emoji


state = NodeState()
ask_user_for_follow_event = asyncio.Event()
user_replied_event = asyncio.Event()
qkd_result_received_event = asyncio.Event()


def get_state() -> NodeState:
    return state
