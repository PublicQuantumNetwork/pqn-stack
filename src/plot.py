import re
import pandas as pd
import matplotlib.pyplot as plt
from pqnstack.constants import DEFAULT_SETTINGS

filename = "../data/1778031771_2026-05-05_20-42-51_R2_I1-O16.csv"
INPUT_PORT = 1
OUTPUT_PORT = 16

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

# Filter to only 500<=t<=50000
df = df[(df["time_from_zero"] >= 500) & (df["time_from_zero"] <= 50000)]

# Split df into 6 dataframes, one for each polarization
dfs = {pol: df[df['polarization'] == pol] for pol in DEFAULT_SETTINGS}

for state in DEFAULT_SETTINGS:
    fig, ax1 = plt.subplots(figsize=(10, 5))
    ax1.set_xlabel("Time (s)")
    ax1.set_ylabel("Ellipticity (°)", color="blue")
    ax1.tick_params(axis="y", labelcolor="blue")
    ax1.grid(True, which="major", linestyle="--", linewidth=0.5, alpha=0.7)
    ax1.plot(dfs[state]["time_from_zero"], dfs[state]["pax_ellipticity_deg"], color="blue", label="Ellipticity (°)", marker="o", markersize=3, linewidth=1)

    ax2 = ax1.twinx()
    ax2.set_ylabel("Azimuth (°)", color="green")
    ax2.tick_params(axis="y", labelcolor="green")
    ax2.plot(dfs[state]["time_from_zero"], dfs[state]["pax_azimuth_deg"], color="green", label="Azimuth (°)", marker="s", markersize=3, linewidth=1)

    plt.title(f"Tomography Data - {state} Light, In {INPUT_PORT} / Out {OUTPUT_PORT}")

    # Save to PNG
    plt.savefig(filename.replace(".csv", f"_{state}.png"), dpi=150, bbox_inches="tight")