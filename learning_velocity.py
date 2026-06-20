"""
learning_velocity.py
====================
How fast does a bitemporal series converge to its final value?

Every revision event advances the knowledge clock. The question is how many
such advances it takes before the published value stabilises. The convergence
curve measures this: for a given period, it tracks what fraction of the total
revision has arrived at each vintage, indexed by months since first publication.

A fast-converging series -- like a restatement driven by a single investigation --
jumps to near-final in the first revision event. A slow-converging series
-- like a Census benchmark that gradually accumulates sample data -- creeps
toward its final value over years.

Functions:
    convergence_curve(series, period)       -- fraction revised at each vintage lag
    half_life(series, period)               -- months until 50% of revision arrived
    estate_velocity(series)                 -- half-life for every revised period
    compare_domains(*series_list, labels)   -- side-by-side domain comparison

The Shell 2004 reserves restatement and the BLS unemployment series sit at
opposite ends of the spectrum: Shell's half-life is bounded at ≤ 7 months
(87% of the revision arrived in the first restatement), while the UNRATE
panel with 5 vintages gives us an upper bound of 62–89 months.
"""

from __future__ import annotations

import os
from typing import Optional

import numpy as np
import pandas as pd

from bitemporal import BitemporalSeries

HERE = os.path.dirname(os.path.abspath(__file__))
FIGURES = os.path.join(HERE, "figures")


def convergence_curve(series: BitemporalSeries, period: str) -> pd.Series:
    """Fraction of total revision accumulated at each vintage, by lag from first release.

    Indexed by months since first publication. Starts at 0.0 (no revision has
    arrived at lag 0 by definition) and converges toward 1.0 as the knowledge
    clock advances.

    A period with total_revision == 0 that nonetheless has multiple vintages
    returns an empty Series -- there is nothing to converge toward.

    Returns an empty Series for periods with fewer than 2 distinct vintages.
    """
    hist = series.revision_history(period)
    if len(hist) < 2:
        return pd.Series(dtype="float64")
    first_val  = float(hist.iloc[0]["value"])
    final_val  = float(hist.iloc[-1]["value"])
    total = final_val - first_val
    if total == 0:
        return pd.Series(dtype="float64")
    first_date = hist.iloc[0]["vintage_date"]
    lags, fracs = [], []
    for _, row in hist.iterrows():
        lag = (
            (row["vintage_date"].year - first_date.year) * 12
            + (row["vintage_date"].month - first_date.month)
        )
        frac = (row["value"] - first_val) / total
        lags.append(lag)
        fracs.append(round(float(frac), 6))
    return pd.Series(fracs, index=lags, name=str(period)[:10])


def half_life(series: BitemporalSeries, period: str) -> Optional[float]:
    """Months from first release until 50% of the total revision has arrived.

    For a step-function convergence curve (common with sparse vintage panels),
    this returns the first lag at which the absolute fraction is >= 0.5.
    This is an upper bound: the true 50% crossover may have occurred between
    the previous and current vintage date.

    Returns None if the period never revised or the curve never crosses 0.5
    (revision is tiny or only one vintage exists).
    """
    if series.total_revision(period) is None:
        return None
    if abs(series.total_revision(period)) == 0:
        return None
    curve = convergence_curve(series, period)
    if curve.empty or len(curve) < 2:
        return None
    crossed = curve[curve.abs() >= 0.5]
    if crossed.empty:
        return None
    return float(crossed.index[0])


def estate_velocity(series: BitemporalSeries) -> pd.DataFrame:
    """Half-life computed for every revised period across the estate.

    Returns a DataFrame with columns:
        period, total_revision, n_revisions, half_life_months.
    Periods with no computable half-life (step functions that never crossed 50%
    before the final vintage) carry NaN.
    """
    rev = series.revised_periods()
    if rev.empty:
        return pd.DataFrame()
    rows = []
    for _, r in rev.iterrows():
        hl = half_life(series, str(r["period"].date()))
        rows.append({
            "period":          r["period"],
            "total_revision":  r["total_revision"],
            "n_revisions":     r["n_revisions"],
            "half_life_months": hl,
        })
    return pd.DataFrame(rows).sort_values("period").reset_index(drop=True)


def compare_domains(
    *series_list: BitemporalSeries, labels: list[str]
) -> pd.DataFrame:
    """Side-by-side half-life summary statistics across multiple domains.

    Returns one row per domain with:
        domain, n_revised, mean_half_life, median_half_life,
        max_half_life, pct_converged_12mo.

    pct_converged_12mo is the fraction of revised periods whose half-life
    is <= 12 months -- a proxy for "this data source converges within one year."
    """
    rows = []
    for s, label in zip(series_list, labels):
        ev = estate_velocity(s)
        if ev.empty:
            continue
        hl = ev["half_life_months"].dropna()
        rows.append({
            "domain":           label,
            "n_revised":        len(ev),
            "n_with_half_life": len(hl),
            "mean_half_life":   round(float(hl.mean()), 1) if len(hl) else float("nan"),
            "median_half_life": round(float(hl.median()), 1) if len(hl) else float("nan"),
            "max_half_life":    round(float(hl.max()), 1) if len(hl) else float("nan"),
            "pct_converged_12mo": round(float((hl <= 12).mean()), 3) if len(hl) else float("nan"),
        })
    return pd.DataFrame(rows)


# ------------------------------------------------------------------ #
# Standalone demo + figure generation
# ------------------------------------------------------------------ #
if __name__ == "__main__":
    import matplotlib as mpl
    import matplotlib.pyplot as plt
    mpl.use("Agg")
    mpl.rcParams.update({"font.family": "serif", "axes.grid": False,
                         "axes.spines.top": False, "axes.spines.right": False})

    from reserves import load_shell_reserves

    csv_path = os.path.join(HERE, "data", "unrate_vintages.csv")
    unrate = BitemporalSeries.from_csv(csv_path)
    shell  = load_shell_reserves()

    ev_unrate = estate_velocity(unrate)
    ev_shell  = estate_velocity(shell)

    print("=== UNRATE estate velocity ===")
    print(ev_unrate.to_string(index=False))
    print()
    print("=== Shell reserves estate velocity ===")
    print(ev_shell.to_string(index=False))
    print()

    comparison = compare_domains(unrate, shell, labels=["UNRATE", "Shell Reserves"])
    print("=== Domain comparison ===")
    print(comparison.to_string(index=False))

    # --- fig10: convergence curves ---
    # Left: Shell YE2002 (most data points) -- shows the real step-wise process
    # Right: UNRATE half-life upper bounds -- all step to 1.0 at lag 60-89 months

    shell_ye2002 = BitemporalSeries(
        shell.frame[shell.frame["period"] == pd.Timestamp("2002-12-31")].copy()
    )
    curve_shell = convergence_curve(shell_ye2002, "2002-12-31")

    # Pick a sample of UNRATE periods for the right panel
    sample_periods = ev_unrate.dropna(subset=["half_life_months"]).head(8)

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))

    # Left: Shell YE2002 convergence
    lags = sorted(curve_shell.index)
    ax1.step(lags, [curve_shell[l] for l in lags], where="post",
             color="black", lw=2.2, marker="o", ms=6)
    ax1.axhline(0.5, color="#aaaaaa", lw=0.9, ls="--")
    ax1.text(0.5, 0.52, "50 %", ha="left", va="bottom", fontsize=8.5,
             color="#888888", transform=ax1.get_yaxis_transform())
    ax1.spines["left"].set_position(("outward", 8))
    ax1.spines["bottom"].set_position(("outward", 8))
    ax1.set_xlabel("Months since first publication")
    ax1.set_ylabel("Fraction of total revision arrived")
    ax1.set_ylim(-0.05, 1.1)
    ax1.set_title("Shell YE2002 reserves\n(4 restatement events, 10-month window)",
                  fontsize=10, fontweight="normal", pad=10)

    # Right: UNRATE period convergence curves
    hl_values = ev_unrate["half_life_months"].dropna().values
    ax2.barh(
        range(len(hl_values)),
        hl_values,
        color="black", height=0.7,
    )
    ax2.axvline(12, color="#aaaaaa", lw=0.9, ls="--")
    ax2.text(13, len(hl_values) - 0.5, "12 mo", ha="left", va="top",
             fontsize=8.5, color="#888888")
    ax2.spines["left"].set_position(("outward", 8))
    ax2.spines["bottom"].set_position(("outward", 8))
    ax2.set_xlabel("Half-life upper bound (months)")
    ax2.set_yticks([])
    ax2.set_title("UNRATE revised periods\n(upper bounds: panel has 5 vintages)",
                  fontsize=10, fontweight="normal", pad=10)

    fig.suptitle(
        "Learning velocity: how fast does data converge?\n"
        "Shell restated within months; UNRATE bounds suggest years",
        fontsize=11, fontweight="normal", y=1.02,
    )
    fig.tight_layout()
    out = os.path.join(FIGURES, "fig10_learning_velocity.png")
    fig.savefig(out, dpi=130, bbox_inches="tight")
    print(f"\nwrote {os.path.relpath(out)}")
