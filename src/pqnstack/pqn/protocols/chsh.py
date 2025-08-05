import datetime
import math
from dataclasses import dataclass
from time import sleep

from pqnstack.pqn.drivers.rotator import RotatorInstrument
from pqnstack.pqn.drivers.timetagger import TimeTaggerInstrument
from pqnstack.pqn.protocols.measurement import CHSHValue
from pqnstack.pqn.protocols.measurement import ExpectationValue
from pqnstack.pqn.protocols.measurement import MeasurementConfig


@dataclass
class Devices:
    idler_hwp: RotatorInstrument
    signal_hwp: RotatorInstrument
    idler_qwp: RotatorInstrument | None
    signal_qwp: RotatorInstrument | None
    timetagger: TimeTaggerInstrument


def calculate_chsh_expectation_error(counts: list[int], dark_count: int = 0) -> float:
    total_counts = sum(counts)
    corrected_total = total_counts - 4 * dark_count
    if corrected_total <= 0:
        return 0
    first_term = math.sqrt(total_counts) / corrected_total
    expectation = abs(counts[0] + counts[3] - counts[1] - counts[2])
    second_term = (expectation / corrected_total**2) * math.sqrt(total_counts + 4 * dark_count)
    return first_term + second_term


def calculate_chsh_error(error_values: list[float]) -> float:
    return math.sqrt(sum(x**2 for x in error_values))


def basis_to_wp(basis: float) -> list[float]:
    return [basis / 2, 0.0]  # TODO: Make input a complex number and have the quarter waveplate angle calculated from it


def measure_expectation_value(
    devices: Devices, config: MeasurementConfig, base1: float, base2: float
) -> ExpectationValue:
    idler_wp_angles = basis_to_wp(base1)
    signal_wp_angles = basis_to_wp(base2)

    angles_idler = [idler_wp_angles, [idler_wp_angles[0] + 45, idler_wp_angles[1]]]
    angles_signal = [signal_wp_angles, [signal_wp_angles[0] + 45, signal_wp_angles[1]]]

    coincidence_counts = []
    for angle_idler in angles_idler:
        for angle_signal in angles_signal:
            devices.idler_hwp.move_to(angle_idler[0])
            devices.signal_hwp.move_to(angle_signal[0])
            if devices.idler_qwp is not None:
                devices.idler_qwp.move_to(angle_idler[1])
            if devices.signal_qwp is not None:
                devices.signal_qwp.move_to(angle_signal[1])
            sleep(2)
            counts = devices.timetagger.measure_correlation(
                config.channel1, config.channel2, int(config.integration_time_s), int(config.binwidth_ps)
            )
            coincidence_counts.append(counts)

    numerator = coincidence_counts[0] - coincidence_counts[1] - coincidence_counts[2] + coincidence_counts[3]
    denominator = sum(coincidence_counts) - 4 * config.dark_count
    expectation_val = 0 if denominator == 0 else numerator / denominator
    expectation_error = calculate_chsh_expectation_error(coincidence_counts, config.dark_count)

    return ExpectationValue(
        timestamp=datetime.datetime.now(datetime.UTC).isoformat(),
        input_base1=base1,
        input_base2=base2,
        idler_wp_angles=angles_idler,
        signal_wp_angles=angles_signal,
        raw_counts=coincidence_counts,
        error=expectation_error,
        value=expectation_val,
    )


def measure_chsh(basis1: list[float], basis2: list[float], devices: Devices, config: MeasurementConfig) -> CHSHValue:
    expectation_values = []
    expectation_errors = []
    raw_results = []

    for base1 in basis1:
        for base2 in basis2:
            raw = measure_expectation_value(devices, config, base1, base2)
            expectation_values.append(raw.value)
            expectation_errors.append(raw.error)
            raw_results.append(raw)

    chsh_value = -1 * expectation_values[0] + expectation_values[1] + expectation_values[2] + expectation_values[3]
    chsh_error = calculate_chsh_error(expectation_errors)

    return CHSHValue(
        timestamp=datetime.datetime.now(datetime.UTC).isoformat(),
        raw_results=raw_results,
        basis1=basis1,
        basis2=basis2,
        chsh_value=chsh_value,
        chsh_error=chsh_error,
    )
