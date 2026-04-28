import datetime
import time
from dataclasses import dataclass
from pqnstack.pqn.drivers.thorlabs_polarimeter import PAX1000IR2
from pqnstack.pqn.drivers.rotator import RotatorInstrument
from pqnstack.constants import DEFAULT_SETTINGS
from pqnstack.constants import MeasurementBasis
from pqnstack.pqn.protocols.measurement import MeasurementConfig

_TOMOGRAPHY_STATES: list[str] = ["H", "V", "D", "A", "R", "L"]

TOMOGRAPHY_BASIS: MeasurementBasis = MeasurementBasis(
    name="TOMOGRAPHY",
    pairs=[(s, i) for s in _TOMOGRAPHY_STATES for i in _TOMOGRAPHY_STATES],
    settings=DEFAULT_SETTINGS,
)


@dataclass
class Devices:
    signal_hwp: RotatorInstrument
    signal_qwp: RotatorInstrument
    polarimeter: PAX1000IR2


@dataclass
class TomographyValue:
    timestamp: str
    tomography_values: dict[str, dict[str, float]]


def measure_tomography_raw(
    devices: Devices,
    config: MeasurementConfig,
    sleepTime: int,
) -> TomographyValue:
    tomography_values = TomographyValue()

    for index, (signal_state, idler_state) in enumerate(TOMOGRAPHY_BASIS.pairs):
        signal_angles: tuple[float, float] = TOMOGRAPHY_BASIS.settings[signal_state]

        devices.signal_hwp.move_to(signal_angles[0])
        devices.signal_qwp.move_to(signal_angles[1])

        time.sleep(sleepTime)

        tomography_values.tomography_values.append(index, devices.polarimeter.read())

    current_time: str = datetime.datetime.now(datetime.UTC).isoformat()

    return TomographyValue(
        timestamp=current_time,
        tomography_value=tomography_values,
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
