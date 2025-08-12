import logging
import os
import tomllib
from pathlib import Path

from dotenv import load_dotenv
from pydantic import BaseModel
from pydantic import Field

from pqnstack.constants import BellState
from pqnstack.constants import QKDEncodingBasis
from pqnstack.pqn.protocols.measurement import MeasurementConfig

load_dotenv()


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


class Settings(BaseModel):
    router_name: str
    router_address: str
    router_port: int
    chsh_settings: CHSHSettings
    qkd_settings: QKDSettings
    bell_state: BellState = BellState.Phi_plus
    timetagger: tuple[str, str] | None = None  # Name of the timetagger to use for the CHSH experiment.


def load_settings_from_toml(config_path: str | Path) -> Settings:
    """Load settings from a TOML configuration file with Pydantic validation."""
    config_path = Path(config_path)

    with Path.open(config_path, "rb") as f:
        config_data = tomllib.load(f)

    # Pydantic will handle all validation and type conversion automatically
    return Settings(**config_data)


def get_settings() -> Settings:
    """Load settings from the config file specified in API_CONFIG_PATH environment variable."""
    config_path = os.getenv("API_CONFIG_PATH")

    if config_path is None:
        logger.warning("API_CONFIG_PATH environment variable not found, using default value './config.toml'")
        config_path = "./config.toml"

    config_file = Path(config_path)
    if not config_file.exists():
        msg = f"Configuration file not found: {config_file.absolute()} or 'API_CONFIG_PATH' environment variable is not set"
        raise FileNotFoundError(msg)

    return load_settings_from_toml(config_path)


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
