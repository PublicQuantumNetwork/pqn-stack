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

def log_data(data):
    global log_filename
    headers = ["timestamp", "pm1_w", "pm1_ref_w", "pm1_total_w", "pax_wavelength_nm"]
    
    with open(log_filename, mode="a", newline="", buffering=1) as file:
        writer = csv.DictWriter(file, fieldnames=headers)

        # Write header if new file
        if file.tell() == 0:
            writer.writeheader()

        writer.writerow(data)
    
for i in range(6000):
    data = meter.read()
    data["timestamp"] = str(time.time())
    log_data(data)

    time.sleep(0.1)
