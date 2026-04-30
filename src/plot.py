import matplotlib.pyplot as plt
import pandas as pd

df = pd.read_csv("tomography_1777573646_R1_H.csv") # read csv into dataframe
df["time_from_zero"] = df["timestamp"] - df["timestamp"].iloc[0] # add new col for time_from_zero, iloc[0] is the value of 1st timestamp

fig, ax1 = plt.subplots() # create figure

ax1.plot(df["time_from_zero"], df["pax_ellipticity_deg"], color="blue", label="Ellipticity (°)")
ax1.set_xlabel("Time (s)") # set x label
ax1.set_ylabel("Ellipticity (°)", color="blue") # set y label

ax2 = ax1.twinx() # add additional axis
ax2.plot(df["time_from_zero"], df["pax_azimuth_deg"], color="red", label="Azimuth (°)") # set x label
ax2.set_ylabel("Azimuth (°)", color="red") # set y label

plt.title("Tomography Data - H Light, Initial Run") # set title
plt.show() # render plot

