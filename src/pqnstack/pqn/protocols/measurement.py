from dataclasses import dataclass

from pydantic import BaseModel


class MeasurementConfig(BaseModel):
    integration_time_s: float
    binwidth_ps: int = 500
    channel1: int = 1
    channel2: int = 2
    dark_count: int = 0


@dataclass
class ExpectationValue:
    timestamp: str
    input_base1: float
    input_base2: float
    idler_wp_angles: list[list[float]]
    signal_wp_angles: list[list[float]]
    raw_counts: list[int]
    error: float
    value: float


@dataclass
class CHSHValue:
    timestamp: str
    raw_results: list[ExpectationValue]
    basis1: list[float]
    basis2: list[float]
    chsh_value: float
    chsh_error: float


@dataclass(frozen=True)
class MeasurementBasis:
    name: str
    pairs: list[tuple[str, str]]
    settings: dict[str, tuple[float, float]]


DEFAULT_SETTINGS: dict[str, tuple[float, float]] = {
    "H": (0, 0),
    "V": (45, 0),
    "D": (22.5, 0),
    "A": (-22.5, 0),
    "R": (22.5, 45),
    "L": (-22.5, 45),
}

HV_BASIS = MeasurementBasis(
    name="HV",
    pairs=[("H", "H"), ("H", "V"), ("V", "H"), ("V", "V")],
    settings=DEFAULT_SETTINGS,
)

DA_BASIS = MeasurementBasis(
    name="DA",
    pairs=[("D", "D"), ("D", "A"), ("A", "D"), ("A", "A")],
    settings=DEFAULT_SETTINGS,
)

RL_BASIS = MeasurementBasis(
    name="RL",
    pairs=[("R", "R"), ("R", "L"), ("L", "R"), ("L", "L")],
    settings=DEFAULT_SETTINGS,
)
