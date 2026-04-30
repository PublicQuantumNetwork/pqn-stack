import os
import csv
import time
import logging
from pqnstack.network.client import Client
from pqnstack.pqn.drivers.switch import Switch
from pqnstack.pqn.drivers.powermeter import PM100D
from tomography import Devices, measure_tomography_raw
from pqnstack.pqn.drivers.rotator import SerialRotator
from pqnstack.pqn.drivers.thorlabs_polarimeter import PAX1000IR2

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

# Output filename
# TODO: need to specify which run we are in somewhere
log_filename = f"tomography_{int(time.time())}.csv"

hwp = SerialRotator(name='hwp', desc='polarization meas setup', hw_address="/dev/ttyACM0")
qwp = SerialRotator(name='qwp', desc='polarization meas setup', hw_address="/dev/ttyUSB0")
hwp.start()
qwp.start()

# TODO: what to set for board and pins?
polarimeter = PAX1000IR2(name="polarimeter", desc="polarimeter", hw_address="/dev/usbtmc0")
polarimeter.start()

switch = Switch("switch", "POLATIS test unit", "192.168.0.1", 8008, "admin", "root")
switch.start()

def log_data(data):
    global log_filename
    
    # TODO: change this to match new data format
    headers = ["timestamp", "pm1_w", "pm1_ref_w", "pm1_total_w", "pax_wavelength_nm"]
    
    with open(log_filename, mode="a", newline="", buffering=1) as file:
        writer = csv.DictWriter(file, fieldnames=headers)

        # Write header if new file
        if file.tell() == 0:
            writer.writeheader()

        writer.writerow(data)

"""
RUN 2
Gather tomography data over 1 hour
EO converter goes to switch input port, switch output goes to meter
"""
def run_two(input_port, output_port):
    global switch, polarimeter, signal_hwp, signal_qwp

    # Remove all patches
    for i in range(8):
        switch.remove_patch(i+1)

    switch.add_patch(inputport, output_port)

    # Repeat once for each polarization state
    for signal_state, idler_state in TOMOGRAPHY_BASIS.pairs:
        signal_angles: tuple[float, float] = TOMOGRAPHY_BASIS.settings[signal_state]
        idler_angles: tuple[float, float] = TOMOGRAPHY_BASIS.settings[idler_state]

        signal_hwp.move_to(signal_angles[0])
        signal_qwp.move_to(signal_angles[1])

        time.sleep(3)

        data = meter.read()
        data["timestamp"] = str(time.time())
        print(polarimeter.read()) # TODO: figure out data format and add it into data{}
        log_data(data)

"""
RUN 3
Measures 1 sample, then rotates, repeat for 10 minutes
"""
def run_three(input_port, output_port):
    global switch, polarimeter, signal_hwp, signal_qwp

    devices = Devices(
        signal_hwp=signal_hwp,
        signal_qwp=signal_qwp,
        timetagger=timetagger
    )
    config = MeasurementConfig(channel1=1, channel2=2, binwidth=1_000, duration=0.5)

    for i in range(200):
        # TODO: figure out data format and log it
        print(measure_tomography_raw(devices, config, 3))

"""
RUN 4
Measure crosstalk
"""
def run_four():
    pass # TODO

"""
RUN 5
Measure extinction ratio
"""
def run_five():
    pass # TODO

try:
    pass
    #run_two(1, 9)
    #run_three(1, 9)
except KeyboardInterrupt:
    pass

if (polarimeter):
    polarimeter.close()
