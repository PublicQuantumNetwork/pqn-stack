import os
import csv
import time
import logging
import tomography
from pqnstack.pqn.drivers.switch import Switch
from pqnstack.pqn.drivers.thorlabs_polarimeter import PAX1000IR2
from pqnstack.pqn.drivers.powermeter import PM100D
from pqnstack.pqn.drivers.rotator import RotatorInstrument
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

log_filename = f"tomography_noswitch_{int(time.time())}.csv"

# Measure data without the switch in the equation
meter = PM100D("mymeter", "PM100D", "/dev/usbtmc1")
meter.start()

switch = Switch("192.168.0.1", 8008, "admin", "root")

# TODO: what to set for board and pins
polarimeter = PAX1000IR2("?", "?", "/dev/?")
polarimeter.start()

# TODO: does this work?
signal_hwp = SerialRotator(offset_degrees=0.0)
signal_hwp.start()
signal_qwp = SerialRotator(offset_degrees=0.0)
signal_qwp.start()



def log_data(data):
    global log_filename
    headers = ["timestamp", "pm1_w", "pm1_ref_w", "pm1_total_w", "pax_wavelength_nm"]
    
    with open(log_filename, mode="a", newline="", buffering=1) as file:
        writer = csv.DictWriter(file, fieldnames=headers)

        # Write header if new file
        if file.tell() == 0:
            writer.writeheader()

        writer.writerow(data)

"""
RUNS 1 AND 2
Gather tomography data over 1 hour
Run 1 is just the EO converter going into the meter, no switch in the equation
Run 2 is the EO converter going into the switch input, switch output goes to meter
"""
def run_one_two(input_port, output_port):
    global meter, switch, polarimeter, rotator

    # Remove all patches
    for i in range(8):
        switch.remove_patch(i+1)

    switch.add_patch(inputport, output_port)

    # Repeat 6 times - one for each polarization
    for i in range(6):

        # Repeat for 10 minutes
        for j in range(6000):
            data = meter.read()
            data["timestamp"] = str(time.time())

            # TODO: figure out data format and add it into data{}
            print(polarimeter.read())
            
            log_data(data)

            time.sleep(0.1)

        # Rotate to next polarization
        # TODO: fix rotations - see soroush code
        rotator.degrees((i+1)*60)

"""
RUN 3
Measures 1 sample, then rotates, repeat for 10 minutes
"""
def run_three(input_port, output_port):
    global meter, switch, polarimeter, rotator



    # # Remove all patches
    # for i in range(8):
    #     switch.remove_patch(i+1)

    # switch.add_patch(inputport, output_port)

    # # Repeat for 10 minutes
    # for j in range(6000):
    #     data = meter.read()
    #     data["timestamp"] = str(time.time())

    #     # TODO: figure out data format and add it into data{}
    #     print(polarimeter.read())
        
    #     log_data(data)

    #     time.sleep(0.1)

    #     # Rotate to next polarization
    #     # TODO: fix rotations - see soroush code
    #     rotator.degrees((i+1)*60)

    # print("Done! Please move to the next switch port combo and run again.")

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
    #run_one_two(1, 9)
    run_three(1, 9)
except KeyboardInterrupt:
    pass

meter.close()
polarimeter.close()
rotator.close()
