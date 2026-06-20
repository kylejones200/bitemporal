"""make_fig3.py -- U.S. unemployment 1948-2025 with Sahm rule firing marks."""
import os
import matplotlib as mpl
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

from bitemporal import BitemporalSeries
from asof_backtest import sahm_trigger

mpl.rcParams.update({"font.family": "serif", "axes.grid": False,
                     "axes.spines.top": False, "axes.spines.right": False})

HERE = os.path.dirname(os.path.abspath(__file__))
OUT  = os.path.join(HERE, "figures", "fig3_series_sahm.png")

s = BitemporalSeries.from_csv(os.path.join(HERE, "data", "unrate_vintages.csv"))
latest = s.snapshot("2025-07-03")
sahm   = sahm_trigger(latest)
fired  = sahm[sahm["triggered"]]

fig, ax = plt.subplots(figsize=(11, 5))
ax.plot(latest.index, latest.values, color="black", lw=1.4)

# Tick marks below the x-axis for every month the Sahm rule fired
ymin = latest.min()
for period in fired.index:
    ax.annotate("", xy=(period, ymin - 0.6), xytext=(period, ymin - 1.2),
                arrowprops=dict(arrowstyle="-", color="#999999", lw=0.8))

ax.spines["left"].set_position(("outward", 8))
ax.spines["bottom"].set_position(("outward", 8))

# 50-year intervals + final year
import pandas as pd
ax.set_xticks([pd.Timestamp("1948-01-01"),
               pd.Timestamp("1998-01-01"),
               pd.Timestamp("2025-06-01")])
ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
ax.set_ylabel("Unemployment rate (%)")
ax.set_title("U.S. unemployment, 1948–2025\n(tick marks: months the Sahm rule fired)",
             fontsize=11, fontweight="normal", pad=14)

fig.tight_layout()
fig.savefig(OUT, dpi=130)
print("wrote", os.path.relpath(OUT))
