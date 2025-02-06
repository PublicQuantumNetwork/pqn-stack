import numpy as np
from time import sleep
import datetime

def calculate_chsh_expectation_error(counts, dark_count=0):
    total_counts = sum(counts)
    corrected_total = total_counts - 4 * dark_count
    sqrt_total_counts = np.sqrt(total_counts)
    first_term = sqrt_total_counts / corrected_total
    expectation = abs(counts[0] + counts[3] - counts[1] - counts[2])
    second_term = (expectation / corrected_total**2) * np.sqrt(total_counts + 4 * dark_count)
    return first_term + second_term

def calculate_chsh_error(error_values):
    return np.sqrt(sum(x**2 for x in error_values))

def basis_to_wp(basis):
    return [basis / 2, 0]

def expectation_value(idler_hwp, idler_qwp, signal_hwp, signal_qwp, timetagger, measurement_duration, binwidth, idler_hwp_angle, idler_qwp_angle, signal_hwp_angle, signal_qwp_angle, channel1 =1, channel2 = 2, dark_count=0):
    angles1 = [
        [idler_hwp_angle, idler_qwp_angle],
        [idler_hwp_angle + 45, idler_qwp_angle]
    ]
    angles2 = [
        [signal_hwp_angle, signal_qwp_angle],
        [signal_hwp_angle + 45, signal_qwp_angle]
    ]
    coincidence_counts = []
    for angle1 in angles1:
        for angle2 in angles2:
            idler_hwp.move_to(angle1[0])
            #idler_qwp.move_to(angle1[1])
            signal_hwp.move_to(angle2[0])
            #signal_qwp.move_to(angle2[1])
            sleep(3)
            counts = timetagger.measure_coincidence(channel1, channel2, int(binwidth * 1e12), int(measurement_duration * 1e12))
            coincidence_counts.append(counts)
    numerator = coincidence_counts[0] - coincidence_counts[1] - coincidence_counts[2] + coincidence_counts[3]
    denominator = sum(coincidence_counts) - 4 * dark_count
    expectation_val = numerator / denominator
    expectation_error = calculate_chsh_expectation_error(coincidence_counts, dark_count)
    raw_results = {
        "timestamp": datetime.datetime.now().isoformat(),
        "input_angles1": angles1,
        "input_angles2": angles2,
        "raw_counts": coincidence_counts,
        "raw_error": expectation_error,
    }
    return expectation_val, expectation_error, raw_results

def measure_chsh(basis1, basis2, 
                idler_hwp, idler_qwp, 
                signal_hwp, signal_qwp, 
                timetagger, measurement_duration, binwidth = 100e-12, 
                channel1 = 1, channel2 = 2, dark_count=0):
    angles1 = [basis_to_wp(element) for element in basis1]
    angles2 = [basis_to_wp(element) for element in basis2]
    expectation_values = []
    expectation_errors = []
    raw_results = []
    for angle1 in angles1:
        for angle2 in angles2:
            exp_val, exp_err, raw = expectation_value(
                idler_hwp,
                idler_qwp,
                signal_hwp,
                signal_qwp,
                timetagger,
                measurement_duration,
                binwidth,
                angle1[0],
                angle1[1],
                angle2[0],
                angle2[1],
                channel1,
                channel2,
                dark_count
            )
            expectation_values.append(exp_val)
            expectation_errors.append(exp_err)
            raw_results.append(raw)
    chsh_value = -1 * expectation_values[0] + expectation_values[1] + expectation_values[2] + expectation_values[3] 
    chsh_error = calculate_chsh_error(expectation_errors)
    results = {
        "timestamp": datetime.datetime.now().isoformat(),
        "raw_results": raw_results,
        "expectation_values": expectation_values,
        "expectation_errors": expectation_errors,
        "basis1": basis1,
        "basis2": basis2,
        "chsh_value": chsh_value,
        "chsh_error": chsh_error,
    }
    #return chsh_value, chsh_error, results
    return results


if __name__ == "__main__":
    from pqnstack.network.client import Client
    c = Client(host = "172.30.63.109", timeout = 30000)
    idler_hwp = c.get_device("loomis_server", "idler_hwp")
    signal_hwp = c.get_device("loomis_server", "signal_hwp")
    timetagger = c.get_device("mini_pc", "tagger")
    print(measure_chsh([0, 45], [22.5, 67.5], idler_hwp, idler_hwp, signal_hwp, signal_hwp, timetagger, 15))
