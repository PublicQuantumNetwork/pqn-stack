from typing import Any


def pq_random(n: int, tagger: Any, input_str: str | None = None) -> int:
    if input_str is not None:
        if not all(c in "01" for c in input_str):
            msg = "Input string must contain only '0's and '1's."
            raise ValueError(msg)
        if n > len(input_str):
            msg = "n cannot be greater than the length of the input string."
            raise ValueError(msg)

    random_bits = []
    for _ in range(n):
        bit = tagger.measure_coincidence(1, 2, 500, int(0.5e12))
        random_bits.append(bit % 2)

    if input_str is not None:
        xor_result = [int(input_str[i]) ^ random_bits[i] for i in range(n)]
        if int("".join(map(str, xor_result)), 2) < 1:
            return 65
        return int("".join(map(str, xor_result)), 2)
    return int("".join(map(str, random_bits)), 2)


if __name__ == "__main__":
    from pqnstack.network.client import Client

    c = Client(host="172.30.63.109", timeout=30000)

    tagger = c.get_device("mini_pc", "tagger")
