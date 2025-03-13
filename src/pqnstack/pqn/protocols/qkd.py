from pqnstack.pqn.drivers.qkd_driver import QKDDevice
from pqnstack.network.client import Client
from pqnstack.network.client import ProxyInstrument
from pqnstack.pqn.protocols.visibility import calculate_visibility

from time import sleep

BASIS_PAIRS: dict[str, list[tuple[str, str]]] = {
    "HV": [("H", "H"), ("H", "V"), ("V", "H"), ("V", "V")],
    "DA": [("D", "D"), ("D", "A"), ("A", "D"), ("A", "A")],
    "RL": [("R", "R"), ("R", "L"), ("L", "R"), ("L", "L")],
}

default_settings: dict[str, tuple[float, float]] = {
    "H": (0, 0),
    "V": (45, 0),
    "D": (22.5, 0),
    "A": (-22.5, 0),
    "R": (22.5, 45),
    "L": (-22.5, 45),
}


def qkd_run(
    qd: ProxyInstrument,
    c: Client,
    basis: str = "HV",
    custom_basis: list[tuple[str, str]] = None,
    custom_settings: dict[str, tuple[float, float]] = None,
    measure_time: float = 10.0,
    player: str = None,
    final: bool = False,
) -> tuple[str, float]:
    """
    Runs a QKD protocol for a single player, independently measuring visibility.

    Parameters:
    - qd: ProxyInstrument (QKD Device instance)
    - c: Client (Network client instance)
    - basis: Basis name ("HV", "DA", "RL") or None for custom basis
    - custom_basis: List of custom measurement pairs (e.g., [("A1", "H"), ("A1", "V"), ("A2", "H"), ("A2", "V")])
    - measure_time: Time to wait before measuring (in seconds)
    - player: Optional player name (if None, it is assigned)

    Returns:
    - Tuple of (player name, measured visibility)
    """

    if player is None:
        player = qd.add_player()
        if not player:
            raise RuntimeError("No available player slots in QKD device.")

    settings = default_settings if custom_settings is None else {**default_settings, **custom_settings}
    key_filter = "signal" if player == "player1" else "idler"  # NOT USELESS, used for motor names for hwp/qwp

    player_motors = qd.get_motors(player)

    motors = {motor: c.get_device(values["location"], values["name"]) for motor, values in player_motors.items()}

    pairs = BASIS_PAIRS.get(basis, custom_basis)
    if pairs is None or len(pairs) != 4:
        raise ValueError("A valid predefined basis or custom basis with exactly four pairs must be provided.")

    coincidence_counts = {}

    for i, (b1, b2) in enumerate(pairs):
        move_state = b1 if i < 2 else b2  # Player 1: B1, B1, B2, B2
        if player == "player2":
            move_state = b1 if i % 2 == 0 else b2  # Player 2: B1, B2, B1, B2

        print(f"settings {settings}")
        print(f"move_state {move_state}")
        print(f"move to {settings[move_state]}")

        if f"{key_filter}_hwp" in motors:
            motors[f"{key_filter}_hwp"].move_to(settings[move_state][0])

        if f"{key_filter}_qwp" in motors:
            motors[f"{key_filter}_qwp"].move_to(settings[move_state][0])

        sleep(2)
        print(f"{player} moved motors to {move_state}")

        qd.submit(player)

        while (counts := qd.get_counts(player)) is None:
            sleep(0.5)

        coincidence_counts[(b1, b2)] = counts

    visibility = calculate_visibility(coincidence_counts, pairs)

    if final:
        qd.remove_player(player)
        player = None

    return player, visibility


if __name__ == "__main__":
    from pqnstack.network.client import Client

    c = Client(host="172.30.63.109", timeout=30000)
    qd = c.get_device("qkd_device", "qd")

    print(qkd_run(qd, c, final=True))
