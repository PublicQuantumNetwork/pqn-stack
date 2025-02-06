import os
import time
import datetime
from pqnstack.network.client import Client
from pqnstack.pqn.protocols.chsh import measure_chsh

def save_measure_chsh_results(file_path, chsh_results):
    with open(file_path, 'a') as file:
        file.write(f"{datetime.datetime.now().isoformat()} - Measure CHSH Results\n")
        for value in chsh_results:
            file.write(f"{value}\n")
        file.write("\n")

def main():
    data_dir = os.path.expanduser("~/data")
    os.makedirs(data_dir, exist_ok=True)
    file_path = os.path.join(data_dir, "chsh_results.txt")
    file_path2 = os.path.join(data_dir, "chsh_long_results.txt")
    
    c = Client(host="172.30.63.109", timeout=30000)
    idler_hwp = c.get_device("loomis_server", "idler_hwp")
    signal_hwp = c.get_device("loomis_server", "signal_hwp")
    timetagger = c.get_device("mini_pc", "tagger")
    
    results_list = []
    start_time = time.time()
    duration = 60 * 60  # 1 hour in seconds
    
    while time.time() - start_time < duration:
        try:
            results = measure_chsh(
                [0, 45], [22.5, 67.5], idler_hwp, idler_hwp, signal_hwp, signal_hwp, timetagger, 15
            )
            results_list.append(results)
            
            save_measure_chsh_results(file_path, results)
            save_measure_chsh_results(file_path2, results_list)
            print(results)
            
        except Exception as e:
            print(f"Error occurred: {e}")
        
        time.sleep(1)  

if __name__ == "__main__":
    main()

