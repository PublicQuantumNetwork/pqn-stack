import datetime
from dataclasses import dataclass
from time import sleep

import numpy as np

from pqnstack.base.driver.rotator import RotatorDevice


@dataclass
class Devices:
    idler_hwp: RotatorDevice
    idler_qwp: RotatorDevice
    signal_hwp: RotatorDevice
    signal_qwp: RotatorDevice
    timetagger: RotatorDevice


@dataclass
class MeasurementConfig:
    duration: float
    binwidth: float = 500e-12
    channel1: int = 1
    channel2: int = 2
    dark_count: int = 0


@dataclass
class Angles:
    idler_hwp: float
    idler_qwp: float
    signal_hwp: float
    signal_qwp: float


def calculate_chsh_expectation_error(counts: list[int], dark_count: int = 0) -> float:
    total_counts = sum(counts)
    corrected_total = total_counts - 4 * dark_count
    sqrt_total_counts = np.sqrt(total_counts)
    first_term = sqrt_total_counts / corrected_total
    expectation = abs(counts[0] + counts[3] - counts[1] - counts[2])
    second_term = (expectation / corrected_total**2) * np.sqrt(total_counts + 4 * dark_count)
    return float(first_term + second_term)


def calculate_chsh_error(error_values: list[float]) -> float:
    return float(np.sqrt(sum(x**2 for x in error_values)))


def basis_to_wp(basis: float) -> list[float]:
    return [basis / 2, 0.0]


def expectation_value(
    devices: Devices, config: MeasurementConfig, angles: Angles
) -> tuple[float, float, dict[str, object]]:
    angles1 = [[angles.idler_hwp, angles.idler_qwp], [angles.idler_hwp + 45, angles.idler_qwp]]
    angles2 = [[angles.signal_hwp, angles.signal_qwp], [angles.signal_hwp + 45, angles.signal_qwp]]
    coincidence_counts = []
    for angle1 in angles1:
        for angle2 in angles2:
            devices.idler_hwp.move_to(angle1[0])
            devices.idler_qwp.move_to(angle1[1])
            devices.signal_hwp.move_to(angle2[0])
            devices.signal_qwp.move_to(angle2[1])
            sleep(2)
            counts = devices.timetagger.measure_coincidence(
                config.channel1, config.channel2, int(config.binwidth * 1e12), int(config.duration * 1e12)
            )
            coincidence_counts.append(counts)
    numerator = coincidence_counts[0] - coincidence_counts[1] - coincidence_counts[2] + coincidence_counts[3]
    denominator = sum(coincidence_counts) - 4 * config.dark_count
    expectation_val = numerator / denominator
    expectation_error = calculate_chsh_expectation_error(coincidence_counts, config.dark_count)
    raw_results = {
        "timestamp": datetime.datetime.now(datetime.UTC).isoformat(),
        "input_angles1": angles1,
        "input_angles2": angles2,
        "raw_counts": coincidence_counts,
        "raw_error": expectation_error,
    }
    return float(expectation_val), expectation_error, raw_results


def measure_chsh(
    basis1: list[float], basis2: list[float], devices: Devices, config: MeasurementConfig
) -> dict[str, object]:
    angles1 = [basis_to_wp(element) for element in basis1]
    angles2 = [basis_to_wp(element) for element in basis2]
    expectation_values = []
    expectation_errors = []
    raw_results = []
    for angle1 in angles1:
        for angle2 in angles2:
            exp_val, exp_err, raw = expectation_value(
                devices, config, Angles(angle1[0], angle1[1], angle2[0], angle2[1])
            )
            expectation_values.append(exp_val)
            expectation_errors.append(exp_err)
            raw_results.append(raw)
    chsh_value = -1 * expectation_values[0] + expectation_values[1] + expectation_values[2] + expectation_values[3]
    chsh_error = calculate_chsh_error(expectation_errors)
    return {
        "timestamp": datetime.datetime.now(datetime.UTC).isoformat(),
        "raw_results": raw_results,
        "expectation_values": expectation_values,
        "expectation_errors": expectation_errors,
        "basis1": basis1,
        "basis2": basis2,
        "chsh_value": chsh_value,
        "chsh_error": chsh_error,
    }
