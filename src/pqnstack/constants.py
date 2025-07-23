from dataclasses import dataclass
from enum import Enum


class QKDAngleValuesHWP(Enum):
    H = 0
    V = 45
    A = -22.5
    D = 22.5


class QKDEncodingBasis(Enum):
    HV = 0
    DA = 1

    @property
    def angles(self) -> list[QKDAngleValuesHWP]:
        if self is QKDEncodingBasis.HV:
            return [QKDAngleValuesHWP.H, QKDAngleValuesHWP.V]
        if self is QKDEncodingBasis.DA:
            return [QKDAngleValuesHWP.D, QKDAngleValuesHWP.A]
        msg = f"Unknown basis: {self}"
        raise ValueError(msg)


class BasisBool(Enum):
    HV = 0
    DA = 1


# FIXME: Populate missing bell states.
class BellState(Enum):
    """Encodes."""

    Phi_plus = 0
    Psi_plus = 1


DEFAULT_SETTINGS: dict[str, tuple[float, float]] = {
    "H": (0, 0),
    "V": (45, 0),
    "D": (22.5, 0),
    "A": (-22.5, 0),
    "R": (22.5, 45),
    "L": (-22.5, 45),
}


@dataclass(frozen=True)
class MeasurementBasis:
    name: str
    pairs: list[tuple[str, str]]
    settings: dict[str, tuple[float, float]]


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
