import re
import matplotlib.pyplot as plt
import pandas as pd

filename = "data/tomography_1777663471_R1_L.csv"

plt.style.use("seaborn-v0_8-white")  # no grid at all by default

# Font sizes
plt.rcParams.update({
    "axes.labelsize": 9,    # x/y axis labels
    "xtick.labelsize": 8,   # x tick numbers
    "ytick.labelsize": 8,   # y tick numbers
    "axes.titlesize": 14,   # title (kept large)
})

df = pd.read_csv(filename)
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

match = re.search(r"R(\d+)_([A-Z]+)", filename)
run_num = match.group(1)
light   = match.group(2)
plt.title(f"Tomography Data - Run {run_num}, {light} Light")

plt.savefig(filename.replace(".csv", ".png"), dpi=150, bbox_inches="tight")