import math
import time
from typing import Any

from pqnstack.constants import MeasurementBasis
from pqnstack.pqn.drivers.rotator import RotatorDevice
from pqnstack.pqn.protocols.measurement import MeasurementConfig


class Devices:
    motors: dict[str, RotatorDevice]
    tagger: Any


def measure_visibility(
    devices: Devices,
    basis: MeasurementBasis,
    config: MeasurementConfig,
) -> tuple[float, float]:
    coincidence_counts: dict[tuple[str, str], int] = {}

    for pair in basis.pairs:
        coincidence_counts[pair] = move_and_measure(
            devices,
            pair[0],
            pair[1],
            basis.settings,
            config,
        )

    return calculate_visibility(coincidence_counts, basis.pairs)


def move_and_measure(
    devices: Devices,
    s_state: str,
    i_state: str,
    settings: dict[str, tuple[float, float]],
    config: MeasurementConfig,
) -> int:
    if s_state not in settings or i_state not in settings:
        msg = f"State {s_state} or {i_state} is not defined in settings."
        raise KeyError(msg)

    for motor_key, angle in [("signal_hwp", settings[s_state][0]), ("idler_hwp", settings[i_state][0])]:
        if motor_key in devices.motors:
            devices.motors[motor_key].move_to(angle)

    if "signal_qwp" in devices.motors or "idler_qwp" in devices.motors:
        for motor_key, angle in [("signal_qwp", settings[s_state][1]), ("idler_qwp", settings[i_state][1])]:
            if motor_key in devices.motors:
                devices.motors[motor_key].move_to(angle)

    time.sleep(2)
    return int(
        devices.tagger.measure_coincidence(
            config.channel1, config.channel2, config.binwidth, int(config.duration * 1e12)
        )
    )


def calculate_visibility(
    coincidence_counts: dict[tuple[str, str], int],
    pairs: list[tuple[str, str]],
) -> tuple[float, float]:
    c_values = [coincidence_counts[pair] for pair in pairs]
    c_max, c_min = max(c_values), min(c_values)

    denominator = (c_max + c_min) ** 2
    if denominator == 0:
        return 0.0, 0.0

    c_err = 2 * math.sqrt((c_min**2) * c_max + (c_max**2) * c_min) / denominator
    return (c_max - c_min) / (c_max + c_min), c_err


"""
Example:

if __name__ == "__main__":
    from pqnstack.network.client import Client

    c = Client(host="172.30.63.109", timeout=300000)
    idler_hwp = c.get_device("loomis_server", "signal_hwp")
    signal_hwp = c.get_device("ufl_closet", "signal_hwp")
    tagger = c.get_device("mini_pc", "tagger")
    motors = {"idler_hwp": idler_hwp, "signal_hwp": signal_hwp}

    devices = Devices(motors=motors, tagger=tagger)
    result = measure_visibility(devices, DA_BASIS)
"""
