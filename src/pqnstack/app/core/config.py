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
from pqnstack.pqn.protocols.measurement import MeasurementConfig

logger = logging.getLogger(__name__)


class CHSHSettings(BaseModel):
    # Specifies which half waveplate to use for the CHSH experiment. First value is the provider's name, second is the motor name.
    hwp: tuple[str, str] = ("", "")
    request_hwp: tuple[str, str] = ("", "")
    measurement_config: MeasurementConfig = Field(default_factory=lambda: MeasurementConfig(integration_time_s=5))


class QKDSettings(BaseModel):
    hwp: tuple[str, str] = ("", "")
    request_hwp: tuple[str, str] = ("", "")
    bitstring_length: int = 4
    discriminating_threshold: int = 10
    measurement_config: MeasurementConfig = Field(default_factory=lambda: MeasurementConfig(integration_time_s=5))


class Settings(BaseSettings):
    router_name: str = "router1"
    router_address: str = "localhost"
    router_port: int = 5555
    chsh_settings: CHSHSettings = CHSHSettings()
    qkd_settings: QKDSettings = QKDSettings()
    bell_state: BellState = BellState.Phi_plus
    timetagger: tuple[str, str] | None = None  # Name of the timetagger to use for the CHSH experiment.

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
