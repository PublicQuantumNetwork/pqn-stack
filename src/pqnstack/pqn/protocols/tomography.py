import datetime
import time
from dataclasses import dataclass

from pqnstack.base.driver.rotator import RotatorDevice
from pqnstack.pqn.drivers.rotator import DEFAULT_SETTINGS
from pqnstack.pqn.drivers.rotator import MeasurementBasis
from pqnstack.pqn.drivers.timetagger import TimeTaggerDevice
from pqnstack.pqn.protocols.measurement import MeasurementConfig

_TOMOGRAPHY_STATES: list[str] = ["H", "V", "D", "A", "R", "L"]

TOMOGRAPHY_BASIS: MeasurementBasis = MeasurementBasis(
    name="TOMOGRAPHY",
    pairs=[(s, i) for s in _TOMOGRAPHY_STATES for i in _TOMOGRAPHY_STATES],
    settings=DEFAULT_SETTINGS,
)


@dataclass
class Devices:
    idler_hwp: RotatorDevice
    idler_qwp: RotatorDevice
    signal_hwp: RotatorDevice
    signal_qwp: RotatorDevice
    timetagger: TimeTaggerDevice


@dataclass
class TomographyValue:
    timestamp: str
    tomography_raw_counts: list[int]


def measure_tomography_raw(
    devices: Devices,
    config: MeasurementConfig,
) -> TomographyValue:
    tomography_counts: list[int] = []

    for signal_state, idler_state in TOMOGRAPHY_BASIS.pairs:
        signal_angles: tuple[float, float] = TOMOGRAPHY_BASIS.settings[signal_state]
        idler_angles: tuple[float, float] = TOMOGRAPHY_BASIS.settings[idler_state]

        devices.signal_hwp.move_to(signal_angles[0])
        devices.signal_qwp.move_to(signal_angles[1])
        devices.idler_hwp.move_to(idler_angles[0])
        devices.idler_qwp.move_to(idler_angles[1])

        time.sleep(3)

        coincidence = devices.timetagger.measure_coincidence(
            config.channel1,
            config.channel2,
            config.binwidth,
            int(config.duration * 1e12),
        )
        tomography_counts.append(int(coincidence))

    current_time: str = datetime.datetime.now(datetime.UTC).isoformat()

    return TomographyValue(
        timestamp=current_time,
        tomography_raw_counts=tomography_counts,
    )


"""
Example:
if __name__ == "__main__":
    from pqnstack.network.client import Client

    client = Client(host="172.30.63.109", timeout=30000)

    idler_hwp = client.get_device("pqn_test3", "idler_hwp")
    idler_qwp = client.get_device("pqn_test3", "idler_qwp")
    signal_hwp = client.get_device("pqn_test3", "signal_hwp")
    signal_qwp = client.get_device("pqn_test3", "signal_qwp")
    timetagger = client.get_device("mini_pc", "tagger")

    devices = Devices(
        idler_hwp=idler_hwp,
        idler_qwp=idler_qwp,
        signal_hwp=signal_hwp,
        signal_qwp=signal_qwp,
        timetagger=timetagger,
    )

    config = MeasurementConfig(channel1=1, channel2=2, binwidth=1_000, duration=0.5)
    result = measure_tomography_raw(devices, config)
"""
