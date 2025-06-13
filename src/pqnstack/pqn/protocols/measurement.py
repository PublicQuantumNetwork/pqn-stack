from dataclasses import dataclass


@dataclass
class MeasurementConfig:
    duration: int  # in picoseconds
    binwidth: int = 500  # in picoseconds
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
