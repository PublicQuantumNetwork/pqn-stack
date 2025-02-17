import math

import pytest
from hypothesis import given
from hypothesis import strategies as st

from pqnstack.pqn.drivers.polarimeter import PolarizationMeasurement


def _theta_to_hvda(theta: float):
    rad = math.radians(theta)
    h = math.cos(rad) ** 2
    d = math.cos(rad + math.pi / 4) ** 2
    v = math.cos(rad + math.pi / 2) ** 2
    a = math.cos(rad + 3 * math.pi / 4) ** 2
    return h, v, d, a


theta = st.floats(0, 360, exclude_max=True)
hvda = theta.map(_theta_to_hvda)


@given(hvda)
def test_polarization_measurement_hvda(hvda):
    h, v, d, a = hvda
    pm = PolarizationMeasurement(*hvda)
    assert pm.h == h
    assert pm.v == v
    assert pm.d == d
    assert pm.a == a


@given(theta)
def test_polarization_measurement_theta(theta: float):
    hvda = _theta_to_hvda(theta)
    pm = PolarizationMeasurement(*hvda, _last_theta=theta)
    diff = (pm.theta - theta) % 360
    assert diff == pytest.approx(0, abs=1e-6) or diff == pytest.approx(360, abs=1e-6)
