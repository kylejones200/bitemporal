"""make_fig2.py -- Revision deltas: the 26 real ±0.1pp corrections."""
import os
import matplotlib as mpl
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import pandas as pd

from bitemporal import BitemporalSeries

mpl.rcParams.update({"font.family": "serif", "axes.grid": False,
                     "axes.spines.top": False, "axes.spines.right": False})

HERE = os.path.dirname(os.path.abspath(__file__))
OUT  = os.path.join(HERE, "figures", "fig2_revision_deltas.png")

s = BitemporalSeries.from_csv(os.path.join(HERE, "data", "unrate_vintages.csv"))
rev = s.revised_periods()
rev = rev[rev["period"] >= pd.Timestamp("2012-01-01")].copy()

fig, ax = plt.subplots(figsize=(10, 4.5))

above = rev[rev["total_revision"] > 0]
below = rev[rev["total_revision"] < 0]
ax.scatter(above["period"], above["total_revision"],
           color="black", s=32, zorder=3, marker="^", label="Revised up")
ax.scatter(below["period"], below["total_revision"],
           color="#888888", s=32, zorder=3, marker="v", label="Revised down")

ax.axhline(0, color="#cccccc", lw=0.8, zorder=1)

ax.spines["left"].set_position(("outward", 8))
ax.spines["bottom"].set_position(("outward", 8))

ax.xaxis.set_major_locator(mdates.YearLocator(2))
ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
ax.set_ylabel("Total revision (pp)")
ax.set_title(
    f"The {len(rev)} revised months between vintages — all exactly ±0.1 percentage point",
    fontsize=11, fontweight="normal", pad=14)
ax.legend(frameon=False, fontsize=9)

fig.tight_layout()
fig.savefig(OUT, dpi=130)
print("wrote", os.path.relpath(OUT))
