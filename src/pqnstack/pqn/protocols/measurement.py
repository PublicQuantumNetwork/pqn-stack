from dataclasses import dataclass

@dataclass
class MeasurementConfig:
    duration: int  # in picoseconds
    binwidth: int = 500  # in picoseconds
    channel1: int = 1
    channel2: int = 2
    dark_count: int = 0

@dataclass(frozen=True)
class MeasurementBasis:
    name: str
    pairs: list[tuple[str, str]]
    settings: dict[str, tuple[float, float]]
