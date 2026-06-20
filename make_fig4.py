"""make_fig4.py -- Shell proved-reserves restatement trajectory (real data)."""
import os
import matplotlib as mpl
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import pandas as pd

from reserves import load_shell_reserves

mpl.rcParams.update({"font.family": "serif", "axes.grid": False,
                     "axes.spines.top": False, "axes.spines.right": False})

HERE = os.path.dirname(os.path.abspath(__file__))
OUT  = os.path.join(HERE, "figures", "fig4_shell_restatement.png")

s = load_shell_reserves()
f = s.frame.sort_values("vintage_date")

fig, ax = plt.subplots(figsize=(10, 5.5))

for anchor, ls, label in [
    (pd.Timestamp("2002-12-31"), "-",  "Proved reserves as of YE2002"),
    (pd.Timestamp("2003-12-31"), "--", "Proved reserves as of YE2003"),
]:
    d = f[f["period"] == anchor]
    ax.step(d["vintage_date"], d["value"], where="post",
            color="black", lw=2, ls=ls, marker="o", ms=5, label=label)
    for _, r in d.iterrows():
        ax.annotate(f"{r['value']:.2f}",
                    (r["vintage_date"], r["value"]),
                    textcoords="offset points", xytext=(6, 7),
                    fontsize=8.5, color="black")

ax.axhline(19.5, color="#bbbbbb", lw=0.9, ls=":")
ax.annotate("originally booked: 19.50 bn boe",
            (pd.Timestamp("2003-08-01"), 19.5),
            textcoords="offset points", xytext=(0, 6),
            fontsize=8, color="#777777")

ax.spines["left"].set_position(("outward", 8))
ax.spines["bottom"].set_position(("outward", 8))

ax.set_ylim(11.5, 20.5)
ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %Y"))
ax.set_ylabel("Proved reserves (billion boe)")
ax.set_title("One fact, many beliefs: Shell's proved reserves restated\n"
             "(the valid-time anchor is fixed; only the knowledge clock moves)",
             fontsize=11, fontweight="normal", pad=14)
ax.legend(frameon=False, fontsize=9)

fig.autofmt_xdate()
fig.tight_layout()
fig.savefig(OUT, dpi=130)
print("wrote", os.path.relpath(OUT))
