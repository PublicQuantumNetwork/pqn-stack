from pqnstack.pqn.drivers.qkd_driver
from pqnstack.pqn.netowork.client import Client
from pqnstack.pqn.netowork.client import ProxyInstrument
from pqnstack.pqn.protocols.visibility import calculate_visibility

from time import sleep

BASIS_PAIRS = {
    "HV": [("H", "H"), ("H", "V"), ("V", "H"), ("V", "V")],
    "DA": [("D", "D"), ("D", "A"), ("A", "D"), ("A", "A")],
    "RL": [("R", "R"), ("R", "L"), ("L", "R"), ("L", "L")]
}

def qkd_run(qd: ProxyInstrument, c: Client, basis: str = "HV",
            custom_basis: list[tuple[str, str]] = None,
            measure_time: float = 10.0, player: str = None,
            final: bool = False) -> tuple[str, float]:
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

    key_filter = "signal" if player == "player1" else "idler"

    player_motors = qd.get_motors(player)

    motors = {name: c.get_device(info["node"], info["name"]) for name, info in player_motors.items()}

    pairs = BASIS_PAIRS.get(basis, custom_basis)
    if pairs is None or len(pairs) != 4:
        raise ValueError("A valid predefined basis or custom basis with exactly four pairs must be provided.")

    coincidence_counts = {}

    for i, (b1, b2) in enumerate(pairs):
        move_state = b1 if i < 2 else b2  # Player 1: B1, B1, B2, B2
        if player == "player2":
            move_state = b1 if i % 2 == 0 else b2  # Player 2: B1, B2, B1, B2

        if f"{key_filter}_hwp" in motors:
            motors[f"{key_filter}_hwp"].move_to(move_state[0])

        if f"{key_filter}_qwp" in motors:
            motors[f"{key_filter}_qwp"].move_to(move_state[1])

        sleep(3)
        print(f"{player} moved motors to {move_state}")
        
        qd.submit(player)
#        while qd.check_submission():  # DOUBLE CHECK LOGIC TO SEE IF IT WORKS THE WAY I WANT IT TO ON FUTURE ROUNDS
#            sleep(0.1)

        while (counts := qd.get_counts(player)) is None:
            sleep(0.5)

        coincidence_counts[(b1, b2)] = counts

    visibility = calculate_visibility(coincidence_counts, pairs)
    
    if final:
        qd.remove_player(player)
        player = None

    return player, visibility
