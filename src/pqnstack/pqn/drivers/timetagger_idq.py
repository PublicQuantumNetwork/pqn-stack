import zmq
import time
import math

class IDQTimeTagger:
    """
    # Example usage:
    # Initialize with the IP address of your TC
    timetagger = IDQTimeTagger('169.254.99.123')

    # Set delay for a channel
    # timetagger.set_delay(2, 261579000)

    # Get single counts from a channel
    # single_counts = timetagger.get_single_counts(1)

    # Get coincidence counts
    # coincidence_counts = timetagger.get_coincidence_counts(5000)
    """

    def __init__(self, ip="169.254.99.123", port=5555):
        self.addr = f"tcp://{ip}:{port}"
        self.context = zmq.Context()
        self.timecontroller = self.context.socket(zmq.REQ)
        self.timecontroller.connect(self.addr)

    def send_command(self, command):
        self.timecontroller.send_string(command)
        return self.timecontroller.recv().decode("utf-8")

    def set_delay(self, channel, delay):
        command = f"INPU{channel}:DELAY {delay}"
        self.send_command(command)

    def get_single_counts(self, channel) -> int:
        command = f"INPU{channel}:COUN?"
        return int(self.send_command(command))

    def get_coincidence_counts(self, interval, channel1, channel2) -> int:
        command = f"TSCO6:LINK {channel1}; TSCO6:LINK {channel2}; TSCO6:COUN:INTE {interval}"
        self.send_command(command)
        command = "TSCO6:COUN?"
        return int(self.send_command(command))

    def check_tsco_num(self, channel1, channel2):
        tsco_nums = []
        command = f"TSCO6:LINK {channel1}; TSCO6:LINK {channel2}; TSCO6:COUN:INTE 1000"
        self.send_command(command)
        command = "TSCO6:COUN?"
        dump_value = int(self.send_command(command))
       
        for i in range(1, 25):
            time.sleep(1)
            command = f"TSCO{i}:LINK {channel1}; TSCO6:LINK {channel2}; TSCO6:COUN:INTE 1000" 
            self.send_command(command)
            command = f"TSCO{i}:COUN?"
            print(command)
            tsco_nums.append(self.send_command(command))
        return tsco_nums

    def _set_histogram_settings(self, min_val, bin_count, bin_width):
        min_val_rounded = round(min_val / 100) * 100
        bin_width_rounded = round(bin_width / 100) * 100
        print(f"Setting histogram settings to multiples of 100 ps: min_val = {min_val_rounded}, bin_width = {bin_width_rounded}")
        
        for i in range(1,5):
             command = f"HIST{i}:MIN {min_val_rounded}; HIST{i}:BWID {bin_width_rounded}; HIST{i}:BCOU {bin_count}"
             print(self.send_command(command))

    def run_histogram(self, min_val, max_val, bin_width, duration):
        bin_width_rounded = round(bin_width / 100) * 100
        bin_count = math.ceil((max_val - min_val) / bin_width_rounded)
        print(f"Calculated bin_count: {bin_count}")

        self._set_histogram_settings(min_val, bin_count, bin_width)

        for i in range(1,5):
            self.send_command(f"HIST{i}:FLUS")

        self.send_command(f"REC:ENAB ON")
        self.send_command(f"REC1:DUR {duration * 1_000_000_000}")  # Convert duration to picoseconds because I want duration to be entered in seconds 
        self.send_command("REC:PLAY")
        time.sleep(duration)
        self.send_command("REC:STOP")

        histogram_data = self.send_command("HIST1:DATA?")
        return histogram_data

    def set_channel_aquis(self, channel, value):
        command = f"INPU{channel}:COUN:INTE {value}"
        return self.send_command(command)


if __name__ == "__main__":
    timetagger = IDQTimeTagger()
    print(timetagger)
    duration = input("Check for how long in miliseconds: ")
    print(timetagger.get_coincidence_counts(duration))
