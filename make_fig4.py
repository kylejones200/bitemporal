"""Make figure 4: Shell proved-reserves restatement trajectory (real data)."""
import os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import pandas as pd

from reserves import load_shell_reserves

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "figures", "fig4_shell_restatement.png")

s = load_shell_reserves()
f = s.frame.sort_values("vintage_date")

fig, ax = plt.subplots(figsize=(10.5, 6))

for anchor, color, label in [
    (pd.Timestamp("2002-12-31"), "#b3122f", "Proved reserves as of YE2002"),
    (pd.Timestamp("2003-12-31"), "#1f4e79", "Proved reserves as of YE2003"),
]:
    d = f[f["period"] == anchor]
    ax.step(d["vintage_date"], d["value"], where="post", color=color, lw=2.4,
            marker="o", ms=7, label=label)
    for _, r in d.iterrows():
        ax.annotate(f"{r['value']:.2f}", (r["vintage_date"], r["value"]),
                    textcoords="offset points", xytext=(6, 8),
                    fontsize=9, color=color, fontweight="bold")

# the originally-reported level, to show how far it fell
ax.axhline(19.5, color="#b3122f", ls=":", lw=1, alpha=0.6)
ax.annotate("originally booked: 19.50 bn boe", (pd.Timestamp("2003-07-15"), 19.5),
            textcoords="offset points", xytext=(0, 6), fontsize=8.5,
            color="#b3122f", alpha=0.9)

ax.set_title("One fact, many beliefs: Shell's proved reserves restated\n"
             "(the valid-time anchor is fixed; only the knowledge clock moves)",
             fontsize=12.5)
ax.set_ylabel("Proved reserves (billion boe)")
ax.set_xlabel("Knowledge date (when the estimate became the official answer)")
ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %Y"))
ax.set_ylim(11.5, 20.5)
ax.legend(loc="upper right", frameon=False)
ax.grid(True, alpha=0.25)
fig.autofmt_xdate()
fig.tight_layout()
fig.savefig(OUT, dpi=130)
print("wrote", os.path.relpath(OUT))
