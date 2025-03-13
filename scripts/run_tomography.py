import os
import time
import datetime
from pqnstack.network.client import Client
from pqnstack.pqn.protocols.tomography import measure_tomography_raw


def save_measure_tomography_results(file_path, tomography_results):
    with open(file_path, "a") as file:
        file.write(f"{datetime.datetime.now().isoformat()} - Measure Tomography Results\n")
        for value in tomography_results:
            file.write(f"{value}\n")
        file.write("\n")


def main():
    data_dir = os.path.expanduser("~/data")
    os.makedirs(data_dir, exist_ok=True)
    file_path = os.path.join(data_dir, "tomography_results.txt")
    file_path2 = os.path.join(data_dir, "tomography_long_results.txt")

    c = Client(host="172.30.63.109", timeout=30000)
    idler_hwp = c.get_device("pqn_test3", "idler_hwp")
    idler_qwp = c.get_device("pqn_test3", "idler_qwp")
    signal_hwp = c.get_device("pqn_test3", "signal_hwp")
    signal_qwp = c.get_device("pqn_test3", "signal_qwp")
    timetagger = c.get_device("mini_pc", "tagger")

    results_list = []
    start_time = time.time()
    duration = 60 * 60  # 1 hour in seconds

    while time.time() - start_time < duration:
        try:
            results = measure_tomography_raw(idler_hwp, idler_qwp, signal_hwp, signal_qwp, timetagger, 10)
            results_list.append(results)

            save_measure_tomography_results(file_path, results)
            save_measure_tomography_results(file_path2, results_list)
            print(results)

        except Exception as e:
            print(f"Error occurred: {e}")

        time.sleep(1)


if __name__ == "__main__":
    main()
