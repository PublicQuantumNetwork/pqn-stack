from dataclasses import dataclass
from time import sleep
from typing import cast

from pqnstack.network.client import Client
from pqnstack.network.client import ProxyInstrument
from pqnstack.pqn.drivers.rotator import DEFAULT_SETTINGS
from pqnstack.pqn.drivers.rotator import HV_BASIS
from pqnstack.pqn.drivers.rotator import MeasurementBasis
from pqnstack.pqn.drivers.rotator import RotatorDevice
from pqnstack.pqn.protocols.visibility import calculate_visibility


@dataclass
class Devices:
    qd: ProxyInstrument
    client: Client


def qkd_run(
    devices: Devices,
    basis: MeasurementBasis = HV_BASIS,
    measure_time: float = 10.0,
    player: str | None = None,
) -> float:
    """
    Run a QKD protocol for a single player, independently measuring visibility.

    Parameters
    ----------
    qd : ProxyInstrument
        QKD Device instance.
    client : Client
        Network client instance.
    basis : MeasurementBasis
        Predefined measurement basis (e.g., HV_BASIS, DA_BASIS, RL_BASIS).
    custom_settings : dict[str, tuple[float, float]] | None
        Optional overrides for default HWP/QWP settings. Keys must be state names.
    measure_time : float
        Time to wait (in seconds) for motor settling before each measurement.
    player : str | None
        Optional player name. If None, a new slot will be assigned.
    final : bool
        If True, the player will be removed from the QKD device after measurement.

    Returns
    -------
    visibility
    """
    if player is None:
        player = devices.qd.add_player()
        if not player:
            msg = "No available player slots in QKD device."
            raise RuntimeError(msg)

    settings = DEFAULT_SETTINGS

    key_filter = "signal" if player == "player1" else "idler"

    player_motors = devices.qd.get_motors(player)
    motors: dict[str, RotatorDevice] = {
        motor_name: cast(RotatorDevice, devices.client.get_device(info["location"], info["name"]))
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

        sleep(measure_time)

        devices.qd.submit(player)

        counts: int | None
        while (counts := devices.qd.get_counts(player)) is None:
            sleep(0.5)

        coincidence_counts[(state1, state2)] = counts

    visibility, _ = calculate_visibility(coincidence_counts, basis.pairs)

    devices.qd.remove_player(player)
    player = None

    return visibility


if __name__ == "__main__":
    from pqnstack.network.devices.client import client

    client = client(host="172.30.63.109", timeout=30000)
    qd_device = client.et_device("qkd_device", "devices.qd")
