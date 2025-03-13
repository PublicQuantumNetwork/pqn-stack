from typing import Optional
import numpy as np


def pqxor_random(n: int, input_str: Optional[str] = None, tagger: Optional[object] = None) -> int:
    if input_str is not None:
        if not all(c in "01" for c in input_str):
            raise ValueError("Input string must contain only '0's and '1's.")
        if n > len(input_str):
            raise ValueError("n cannot be greater than the length of the input string.")

    if tagger is not None:
        random_bits = []
        for _ in range(n):
            print(tagger)
            bit = tagger.measure_coincidence(1, 2, 500, int(0.5e12))
            print(bit)
            print(bit % 2)
            random_bits.append(bit % 2)

        if input_str is not None:
            xor_result = [int(input_str[i]) ^ random_bits[i] for i in range(n)]
            print(xor_result)
            print(int("".join(map(str, xor_result)), 2))
            if int("".join(map(str, xor_result)), 2) < 1:
                print("returning 65")
                return 65
            else:
                return int("".join(map(str, xor_result)), 2)
        else:
            return int("".join(map(str, random_bits)), 2)

    if input_str is not None:
        return int(input_str[:n], 2)

    return np.random.randint(1, 2**n)


if __name__ == "__main__":
    from pqnstack.network.client import Client

    c = Client(host="172.30.63.109", timeout=30000)

    tagger = c.get_device("mini_pc", "tagger")

    print(pqxor_random(n=6, tagger=tagger))
