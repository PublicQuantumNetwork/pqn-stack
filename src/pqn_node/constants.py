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
