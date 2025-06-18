from dataclasses import dataclass
from time import sleep
from typing import cast

from pqnstack.network.client import Client
from pqnstack.network.client import ProxyInstrument
from pqnstack.pqn.drivers.rotator import RotatorDevice
from pqnstack.pqn.protocols.measurement import DEFAULT_SETTINGS
from pqnstack.pqn.protocols.measurement import HV_BASIS
from pqnstack.pqn.protocols.measurement import MeasurementBasis
from pqnstack.pqn.protocols.measurement import MeasurementConfig
from pqnstack.pqn.protocols.visibility import calculate_visibility


@dataclass
class Devices:
    qd: ProxyInstrument
    client: Client


def qkd_run(
    devices: Devices,
    config: MeasurementConfig,
    basis: MeasurementBasis = HV_BASIS,
) -> tuple[float, float]:
    """
    Run a QKD protocol for a single player, independently measuring visibility.

    Parameters
    ----------
    devices: Devices
    basis : MeasurementBasis
        Predefined measurement basis (e.g., HV_BASIS, DA_BASIS, RL_BASIS).
    config : MeasurementConfig
        the config for the measurement

    Returns
    -------
    visibility
    """
    player = devices.qd.add_player()
    if not player:
        msg = "No available player slots in QKD device."
        raise RuntimeError(msg)

    settings = DEFAULT_SETTINGS

    key_filter = "signal" if player == "player1" else "idler"

    player_motors = devices.qd.get_motors(player)
    motors: dict[str, RotatorDevice] = {
        motor_name: cast("RotatorDevice", devices.client.get_device(info["location"], info["name"]))
        for motor_name, info in player_motors.items()
    }
    coincidence_counts: dict[tuple[str, str], int] = {}
    for index, (state1, state2) in enumerate(basis.pairs):
        # Determine which state to move for this player
        if player == "player1":  # noqa: SIM108
            move_state = state1 if index < 2 else state2  # noqa: PLR2004
        else:
            move_state = state1 if (index % 2) == 0 else state2

        angles = settings[move_state]
        hwp_angle, qwp_angle = angles

        hwp_key = f"{key_filter}_hwp"
        if hwp_key in motors:
            motors[hwp_key].move_to(hwp_angle)

        qwp_key = f"{key_filter}_qwp"
        if qwp_key in motors:
            motors[qwp_key].move_to(qwp_angle)

        sleep(config.duration)

        devices.qd.submit(player)

        counts: int | None
        while (counts := devices.qd.get_counts(player)) is None:
            sleep(0.5)

        coincidence_counts[(state1, state2)] = counts

    visibility, error = calculate_visibility(coincidence_counts, basis.pairs)

    devices.qd.remove_player(player)

    return visibility, error


if __name__ == "__main__":
    from pqnstack.network.devices.client import client

    client = client(host="172.30.63.109", timeout=30000)
    qd_device = client.et_device("qkd_device", "devices.qd")
