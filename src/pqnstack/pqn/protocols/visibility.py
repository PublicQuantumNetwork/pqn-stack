import time
import math

def measure_visibility(motors: dict, tagger: object, basis: str = 'HV',
                       custom_basis: list[tuple[str, str]] = None,
                       custom_settings: dict[str, tuple[float, float]] = None,
                       wait_time: float = 10.0) -> float:

    default_settings: dict[str, tuple[float, float]] = {
        "H": (0, 0), "V": (45, 0),
        "D": (22.5, 0), "A": (-22.5, 0),
        "R": (22.5, 45), "L": (-22.5, 45)
    }

    settings = default_settings if custom_settings is None else {**default_settings, **custom_settings}

    basis_pairs: dict[str, list[tuple[str, str]]] = {
        "HV": [("H", "H"), ("H", "V"), ("V", "H"), ("V", "V")],
        "DA": [("D", "D"), ("D", "A"), ("A", "D"), ("A", "A")],
        "RL": [("R", "R"), ("R", "L"), ("L", "R"), ("L", "L")]
    }

    pairs: list[tuple[str, str]] = basis_pairs.get(basis, custom_basis)

    if pairs is None:
        raise ValueError("Either a valid predefined basis must be provided, or a custom basis must be specified.")

    coincidence_counts: dict[tuple[str, str], int] = {
        pair: move_and_measure(motors, tagger, *pair, settings, wait_time) for pair in pairs
    }

    return calculate_visibility(coincidence_counts, pairs)

def move_and_measure(motors: dict, tagger: object, s_state: str, i_state: str, 
                     settings: dict[str, tuple[float, float]], wait_time: float) -> int:

    if s_state not in settings or i_state not in settings:
        raise KeyError(f"State {s_state} or {i_state} is not defined in settings.")

    for motor_key, angle in [
        ("signal_hwp", settings[s_state][0]),
        ("idler_hwp", settings[i_state][0])
    ]:
        if motor_key in motors:
            motors[motor_key].move_to(angle)

    if "signal_qwp" in motors or "idler_qwp" in motors:
        for motor_key, angle in [
            ("signal_qwp", settings[s_state][1]),
            ("idler_qwp", settings[i_state][1])
        ]:
            if motor_key in motors:
                motors[motor_key].move_to(angle)

    print(f"Moved motors to: Signal = {s_state} ({settings[s_state]}), Idler = {i_state} ({settings[i_state]})")

    time.sleep(wait_time)

    return tagger.measure_coincidence(1, 2, 100, int(10e12))

def calculate_visibility(coincidence_counts: dict[tuple[str, str], int], 
                         pairs: list[tuple[str, str]]) -> float:
    C_max: int = max(coincidence_counts[pair] for pair in pairs)
    C_min: int = min(coincidence_counts[pair] for pair in pairs)
    error = calculate_visibility_error(C_min, C_max)
    print(f"min count = {C_min}, max count = {C_max}, error in visibility = {error}")

    return (C_max - C_min) / (C_max + C_min) if C_max + C_min > 0 else 0  

def calculate_visibility_error(c_min: int, c_max: int):
   return 2 * math.sqrt(c_min**2 * c_max + c_max**2 * c_min) / (c_max + c_min)**2 
