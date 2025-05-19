import datetime
from dataclasses import dataclass
from time import sleep

import numpy as np

from pqnstack.base.driver.rotator import RotatorDevice

v, h, d, a, r, l = (  # noqa: E741
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


def measure_tomography_raw(
    devices: Devices,
    measurement: MeasurementConfig,
) -> dict[str, object]:
    tomography_results = []
    singles_counts = []
    for i in range(6):
        for j in range(6):
            devices.idler_hwp.move_to(tomography_angles[j][0])
            devices.idler_qwp.move_to(tomography_angles[j][1])
            devices.signal_hwp.move_to(tomography_angles[i][0])
            devices.signal_qwp.move_to(tomography_angles[i][1])
            sleep(3)
            tomography_results.append(
                devices.timetagger.measure_coincidence(
                    measurement.channel1, measurement.channel2, measurement.binwidth, int(measurement.duration * 1e12)
                )
            )
            singles_counts.append(
                devices.timetagger.measure_countrate(
                    [measurement.channel1, measurement.channel2], int(measurement.duration * 1e12)
                )
            )

    current_time = datetime.datetime.now(datetime.UTC).isoformat()
    return {"timestamp": current_time, "tomography_raw_counts": tomography_results, "singles_counts": singles_counts}


if __name__ == "__main__":
    from pqnstack.network.client import Client

    c = Client(host="172.30.63.109", timeout=30000)
    idler_hwp = c.get_device("pqn_test3", "idler_hwp")
    idler_qwp = c.get_device("pqn_test3", "idler_qwp")
    signal_hwp = c.get_device("pqn_test3", "signal_hwp")
    signal_qwp = c.get_device("pqn_test3", "signal_qwp")
    timetagger = c.get_device("mini_pc", "tagger")
