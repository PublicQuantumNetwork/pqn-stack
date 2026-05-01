import os
import re
import csv
import time
import logging
import pandas as pd
from datetime import datetime
import matplotlib.pyplot as plt
from pqnstack.network.client import Client
from pqnstack.pqn.drivers.switch import Switch
from pqnstack.constants import DEFAULT_SETTINGS
from pqnstack.pqn.drivers.powermeter import PM100D
from tomography import Devices, measure_tomography_raw
from pqnstack.pqn.drivers.rotator import SerialRotator
from pqnstack.pqn.drivers.thorlabs_polarimeter import PAX1000IR2

OUTPUT_DIRECTORY = "../data"

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

# Connect to polarimeter
logger.info("Connecting to polarimeter")
polarimeter = PAX1000IR2(name="polarimeter", desc="polarimeter", hw_address="")
polarimeter.start()

# Connect to switch
logger.info("Connecting to switch")
switch = Switch("switch", "POLATIS test unit", "192.168.0.1", 8008, "admin", "root")
switch.start()

# Connect to HWP
logger.info("Connecting to HWP")
hwp = SerialRotator(name='hwp', desc='polarization meas setup', hw_address="/dev/ttyACM0")
hwp.start()

# Connect to QWP
logger.info("Connecting to QWP")
qwp = SerialRotator(name='qwp', desc='polarization meas setup', hw_address="/dev/ttyUSB0")
qwp.start()

# Appends data to the CSV data file
def record_data(data, log_filename):
    # TODO: change this to match new data format
    headers = ["timestamp", "pax_azimuth_deg", "pax_ellipticity_deg", "pax_theta_deg", "pax_eta_deg", "pax_dop", "pax_power_w", "pax_wavelength_nm"]

    # Check if file exists
    file_exists = os.path.exists(log_filename)

    with open(log_filename, mode="a", newline="", buffering=1) as file:
        writer = csv.DictWriter(file, fieldnames=headers)

        # Write header if new file
        if not file_exists:
            writer.writeheader()

        # Append row
        writer.writerow(data)

# Generates a data plot of the specified CSV file
def plot_data(filename):
    # Set theme
    plt.style.use("seaborn-v0_8-white")

    # Set font size
    plt.rcParams.update({
        "axes.labelsize": 9,
        "xtick.labelsize": 8,
        "ytick.labelsize": 8,
        "axes.titlesize": 14,
    })

    # Read CSV into dataframe
    df = pd.read_csv(filename)

    # Offset timestamp column so the first record occurs at t=0
    df["time_from_zero"] = df["timestamp"] - df["timestamp"].iloc[0]

    fig, ax1 = plt.subplots(figsize=(10, 5))
    ax1.plot(df["time_from_zero"], df["pax_ellipticity_deg"], color="blue", label="Ellipticity (°)",
            marker="o", markersize=3, linewidth=1)
    ax1.set_xlabel("Time (s)")
    ax1.set_ylabel("Ellipticity (°)", color="blue")
    ax1.tick_params(axis="y", labelcolor="blue")
    ax1.grid(True, which="major", linestyle="--", linewidth=0.5, alpha=0.7)

    ax2 = ax1.twinx()
    ax2.plot(df["time_from_zero"], df["pax_azimuth_deg"], color="green", label="Azimuth (°)",
            marker="s", markersize=3, linewidth=1)
    ax2.set_ylabel("Azimuth (°)", color="green")
    ax2.tick_params(axis="y", labelcolor="green")

    # Set title using filename
    match = re.search(r"R(\d+)_([A-Z]+)", filename)
    run_num = match.group(1)
    light   = match.group(2)
    plt.title(f"Tomography Data - Run {run_num}, {light} Light")

    # Save to PNG
    plt.savefig(filename.replace(".csv", ".png"), dpi=150, bbox_inches="tight")

# Returns a timestamp in the format "UNIXTIMESTAMP_YYYY-MM-DD_HH-MM-SS" to use in filenames
def get_timestamp():
    now = datetime.now()
    unix_ts = int(now.timestamp())
    readable = now.strftime("%Y-%m-%d_%H-%M-%S")
    return f"{unix_ts}_{readable}"

"""
RUN 1
Measure stability of H input over a 10min period
Repeat for V, D, L, A, R
"""
def run_one(input_port, output_port):
    global switch, polarimeter, hwp, qwp, OUTPUT_DIRECTORY

    # Remove all existing patches
    logger.info("Removing existing patches")
    for i in range(8):
        switch.remove_patch(i+1)

    # Add a new patch from input_port to output_port
    logger.info("Creating new patch")
    switch.add_patch(input_port, output_port)

    for state in DEFAULT_SETTINGS:
        # Output filename
        log_filename = f"{OUTPUT_DIRECTORY}/{get_timestamp()}_R1_{state}.csv"

        # Move HWP and QWP to desired angles
        logger.info(f"Moving rotators to {state} polarization")
        hwp.move_to(DEFAULT_SETTINGS[state][0])
        qwp.move_to(DEFAULT_SETTINGS[state][1])
        time.sleep(1)

        for i in range(60):
            data = polarimeter.read()
            data["timestamp"] = str(time.time())
            record_data(data, log_filename)
            time.sleep(10)

        logger.info(f"Done recording data from {state} polarization")
        plot_data(log_filename)
        logger.info("Generated data plot")

"""
RUN 2
Measure H, V, D, L, A, then R
Wait 10 seconds
Repeat whole process 40 times
"""
def run_two(input_port, output_port):
    global switch, polarimeter, hwp, qwp

    # Remove all patches
    for i in range(8):
        switch.remove_patch(i+1)

    switch.add_patch(inputport, output_port)

    # Repeat once for each polarization state
    for signal_state, idler_state in TOMOGRAPHY_BASIS.pairs:
        signal_angles: tuple[float, float] = TOMOGRAPHY_BASIS.settings[signal_state]
        idler_angles: tuple[float, float] = TOMOGRAPHY_BASIS.settings[idler_state]

        hwp.move_to(signal_angles[0])
        qwp.move_to(signal_angles[1])

        time.sleep(1)

        data = meter.read()
        #data["timestamp"] = str(time.time())
        print(polarimeter.read()) # TODO: figure out data format and add it into data{}
        record_data(data)

"""
RUN 3
Measures 1 sample, then rotates, repeat for 10 minutes
"""
def run_three(input_port, output_port):
    global switch, polarimeter, hwp, qwp

    devices = Devices(
        hwp=hwp,
        qwp=qwp,
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
    run_one(1, 9)
except KeyboardInterrupt:
    logger.warning("Received KeyboardInterrupt - halting")

if (polarimeter):
    polarimeter.close()

# Move HWP and QWP to desired angles
logger.info("Resetting rotators")
hwp.move_to(0)
qwp.move_to(0)
time.sleep(1)
