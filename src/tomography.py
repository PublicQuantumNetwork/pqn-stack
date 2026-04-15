import os
import csv
import time
import logging
from pqnstack.pqn.drivers.switch import Switch
from pqnstack.pqn.drivers.polarimeter import ArduinoPolarimeter
from pqnstack.pqn.drivers.powermeter import PM100D
from pqnstack.pqn.drivers.rotator import SerialRotator
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

log_filename = f"tomography_noswitch_{int(time.time())}.csv"

# Measure data without the switch in the equation
meter = PM100D("mymeter", "PM100D", "/dev/usbtmc1")
meter.start()

# TODO: what to set for board and pins
polarimeter = ArduinoPolarimeter(sample_rate=10, average_width=10, board=None, pins=None)
polarimeter.start()

# TODO: does this work?
rotator = SerialRotator(offset_degrees=0.0)
rotator.start()

def log_data(data):
    global log_filename
    headers = ["timestamp", "pm1_w", "pm1_ref_w", "pm1_total_w", "pax_wavelength_nm"]
    
    with open(log_filename, mode="a", newline="", buffering=1) as file:
        writer = csv.DictWriter(file, fieldnames=headers)

        # Write header if new file
        if file.tell() == 0:
            writer.writeheader()

        writer.writerow(data)
    
try:
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
    rotator.degrees((i+1)*60)

except KeyboardInterrupt:
    pass

meter.close()
polarimeter.close()
rotator.close()
