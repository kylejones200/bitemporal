"""make_fig1.py -- Fan of vintages: the same six years seen from three moments."""
import os
import matplotlib as mpl
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import pandas as pd

from bitemporal import BitemporalSeries

mpl.rcParams.update({"font.family": "serif", "axes.grid": False,
                     "axes.spines.top": False, "axes.spines.right": False})

HERE = os.path.dirname(os.path.abspath(__file__))
OUT  = os.path.join(HERE, "figures", "fig1_fan_of_vintages.png")

s = BitemporalSeries.from_csv(os.path.join(HERE, "data", "unrate_vintages.csv"))

vintages = [("2018-02-02", "2018-01-01", "2018 vintage",  "#aaaaaa", 1.2, "--"),
            ("2020-05-08", "2020-04-01", "2020 vintage",  "#555555", 1.6, "-"),
            ("2025-07-03", "2018-02-01", "2025 vintage",  "#000000", 2.0, "-")]

# Restrict to the window where all three vintages overlap so the ±0.1pp
# divergences are visible at a sensible y-scale.
start, end = pd.Timestamp("2013-01-01"), pd.Timestamp("2018-03-01")

fig, ax = plt.subplots(figsize=(10, 5))
for kd, last_period, label, color, lw, ls in vintages:
    snap = s.snapshot(kd)
    snap = snap[(snap.index >= start) & (snap.index <= pd.Timestamp(last_period))]
    ax.plot(snap.index, snap.values, color=color, lw=lw, ls=ls, label=label)

ax.spines["left"].set_position(("outward", 8))
ax.spines["bottom"].set_position(("outward", 8))
ax.set_xlim(start, end)
ax.set_ylim(3.5, 8.5)

ax.xaxis.set_major_locator(mdates.YearLocator(1))
ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
ax.set_ylabel("Unemployment rate (%)")
ax.set_title("The same five years of unemployment, seen from three moments in time",
             fontsize=11, fontweight="normal", pad=14)
ax.legend(frameon=False, fontsize=9)

fig.tight_layout()
fig.savefig(OUT, dpi=130)
print("wrote", os.path.relpath(OUT))
