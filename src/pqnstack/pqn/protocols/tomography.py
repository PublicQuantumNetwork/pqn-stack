import numpy as np
from time import sleep
import datetime

v, h, d, a, r, l = (
    [45, 0],
    [0, 0],
    [22.5, 0],
    [67.5, 0],
    [0, -45],
    [0, 45],
)

tomography_angles = np.array(
    [
        np.array(h),
        np.array(v),
        np.array(d),
        np.array(a),
        np.array(r),
        np.array(l),
    ]
)


def measure_tomography_raw(
    idler_hwp,
    idler_qwp,
    signal_hwp,
    signal_qwp,
    timetagger,
    measurement_duration,
    binwidth=100,
    channel1=1,
    channel2=2,
    dark_count=0,
):
    tomography_results = []
    singles_counts = []
    for i in range(6):
        for j in range(6):
            idler_hwp.move_to(tomography_angles[j][0])
            idler_qwp.move_to(tomography_angles[j][1])
            signal_hwp.move_to(tomography_angles[i][0])
            signal_qwp.move_to(tomography_angles[i][1])
            sleep(3)
            tomography_results.append(
                timetagger.measure_coincidence(channel1, channel2, binwidth, int(measurement_duration * 1e12))
            )
            singles_counts.append(timetagger.measure_countrate([channel1, channel2], int(measurement_duration * 1e12)))

    current_time = datetime.datetime.now().isoformat()
    results = {"timestamp": current_time, "tomography_raw_counts": tomography_results, "singles_counts": singles_counts}
    return results


if __name__ == "__main__":
    from pqnstack.network.client import Client

    c = Client(host="172.30.63.109", timeout=30000)
    idler_hwp = c.get_device("pqn_test3", "idler_hwp")
    idler_qwp = c.get_device("pqn_test3", "idler_qwp")
    signal_hwp = c.get_device("pqn_test3", "signal_hwp")
    signal_qwp = c.get_device("pqn_test3", "signal_qwp")
    timetagger = c.get_device("mini_pc", "tagger")
    print(measure_tomography_raw(idler_hwp, idler_qwp, signal_hwp, signal_qwp, timetagger, 10))
