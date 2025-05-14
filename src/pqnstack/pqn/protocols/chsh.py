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
    return [basis / 2, 0.0]  # TODO: Make input a complex number and have the quarter waveplate angle calculated from it


def expectation_value(
    devices: Devices, config: MeasurementConfig, base1: float, base2: float
) -> tuple[float, float, dict[str, object]]:
    idler_wp_angles = basis_to_wp(base1)
    signal_wp_angles = basis_to_wp(base2)

    angles_idler = [idler_wp_angles, [idler_wp_angles[0] + 45, idler_wp_angles[1]]]
    angles_signal = [signal_wp_angles, [signal_wp_angles[0] + 45, signal_wp_angles[1]]]

    coincidence_counts = []
    for angle_idler in angles_idler:
        for angle_signal in angles_signal:
            devices.idler_hwp.move_to(angle_idler[0])
            devices.idler_qwp.move_to(angle_idler[1])
            devices.signal_hwp.move_to(angle_signal[0])
            devices.signal_qwp.move_to(angle_signal[1])
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
        "input_base1": base1,
        "input_base2": base2,
        "idler_wp_angles": angles_idler,
        "signal_wp_angles": angles_signal,
        "raw_counts": coincidence_counts,
        "raw_error": expectation_error,
    }

    return float(expectation_val), expectation_error, raw_results


def measure_chsh(
    basis1: list[float], basis2: list[float], devices: Devices, config: MeasurementConfig
) -> dict[str, object]:
    expectation_values = []
    expectation_errors = []
    raw_results = []

    for base1 in basis1:
        for base2 in basis2:
            exp_val, exp_err, raw = expectation_value(devices, config, base1, base2)
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
