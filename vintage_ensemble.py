"""
vintage_ensemble.py
===================
Multiple vintages as an empirical forecast ensemble.

The single number on a press release is a point estimate. If you treat the
revision history of similar periods as a prior, you can replace that point with
a distribution -- and then ask whether the distribution was calibrated.

The core idea:
    1. Collect all historical revision deltas across the full panel.
    2. For any preliminary value v₀, the eventual final value v_final sits
       at v₀ + δ, where δ draws from that empirical distribution.
    3. Report [v₀ + q_low, v₀ + q_high] as the confidence interval.
    4. Back-test coverage: what fraction of preliminary estimates, when given
       this interval, actually contained the eventual final value?

A perfectly calibrated 95% CI covers the final value in 95% of cases.
Under-coverage means the interval is too narrow. Over-coverage means it is
too conservative (wide enough to be uninformative).

Classes:
    VintageEnsemble    -- wraps a BitemporalSeries; builds the empirical ensemble

Functions (used by VintageEnsemble and available standalone):
    uncertainty_band(period, level)    -- (lower, upper) as float tuple
    coverage_rate(level)               -- calibration back-test
    ensemble_snapshot(knowledge_date)  -- full snapshot with bands
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional, Tuple

import numpy as np
import pandas as pd

from bitemporal import BitemporalSeries
from revision_stats import revision_distribution

HERE = os.path.dirname(os.path.abspath(__file__))
FIGURES = os.path.join(HERE, "figures")


@dataclass
class VintageEnsemble:
    """Treat the panel's revision history as a calibration dataset.

    Every method is a function of the empirical distribution of revision deltas
    across the entire panel. With only 26 observations at ±0.1pp, the
    distribution is fully characterized by two mass points. The coverage_rate
    method reveals whether that narrow distribution is calibrated.
    """

    series: BitemporalSeries

    def uncertainty_band(
        self, period: str, level: float = 0.95
    ) -> Optional[Tuple[float, float]]:
        """Empirical CI around the first-release value for `period`.

        Returns (lower, upper) as absolute values, or None if the period
        has not been published yet.
        """
        dist = revision_distribution(self.series)
        if not dist or dist["n"] < 2:
            return None
        first = self.series.first_release(period)
        if first is None:
            return None
        deltas = dist["deltas"]
        alpha = 1 - level
        q_low  = float(np.quantile(deltas, alpha / 2))
        q_high = float(np.quantile(deltas, 1 - alpha / 2))
        return (first + q_low, first + q_high)

    def coverage_rate(self, level: float = 0.95) -> dict:
        """Backtest: fraction of preliminary values whose CI contained the final.

        Returns n_tested, coverage (fraction), level_requested, q_low, q_high.
        A well-calibrated 95% CI should return coverage ≈ 0.95 in large samples.
        """
        rev = self.series.revised_periods()
        if rev.empty:
            return {"coverage": float("nan"), "n_tested": 0}
        dist = revision_distribution(self.series)
        if not dist:
            return {"coverage": float("nan"), "n_tested": 0}
        deltas = dist["deltas"]
        alpha = 1 - level
        q_low  = float(np.quantile(deltas, alpha / 2))
        q_high = float(np.quantile(deltas, 1 - alpha / 2))
        covered = 0
        # Use a small tolerance so boundary-hitting finals count as covered.
        # BLS reports to 1dp, so revisions landing exactly at ±0.1 are expected;
        # floating-point addition (e.g. 4.2 + (-0.1) = 4.1000000000000005)
        # would otherwise incorrectly exclude them.
        eps = 1e-9
        for _, row in rev.iterrows():
            first = row["first_release"]
            final = row["latest"]
            if (first + q_low - eps) <= final <= (first + q_high + eps):
                covered += 1
        n = len(rev)
        return {
            "coverage": covered / n if n > 0 else float("nan"),
            "n_tested": n,
            "n_covered": covered,
            "level_requested": level,
            "q_low": q_low,
            "q_high": q_high,
        }

    def ensemble_snapshot(
        self, knowledge_date: str, level: float = 0.95
    ) -> pd.DataFrame:
        """Full snapshot with empirical uncertainty bands.

        Returns a DataFrame with columns: point_estimate, lower, upper.
        The lower/upper bands reflect the full historical revision distribution,
        not period-specific history (which would require many more vintages).
        """
        snap = self.series.snapshot(knowledge_date)
        dist = revision_distribution(self.series)
        if not dist:
            return snap.to_frame("point_estimate")
        deltas = dist["deltas"]
        alpha = 1 - level
        q_low  = float(np.quantile(deltas, alpha / 2))
        q_high = float(np.quantile(deltas, 1 - alpha / 2))
        return pd.DataFrame({
            "point_estimate": snap.values,
            "lower": snap.values + q_low,
            "upper": snap.values + q_high,
        }, index=snap.index)


# ------------------------------------------------------------------ #
# Standalone demo + figure generation
# ------------------------------------------------------------------ #
if __name__ == "__main__":
    import matplotlib as mpl
    import matplotlib.pyplot as plt
    mpl.use("Agg")
    mpl.rcParams.update({"font.family": "serif", "axes.grid": False,
                         "axes.spines.top": False, "axes.spines.right": False})

    csv_path = os.path.join(HERE, "data", "unrate_vintages.csv")
    s = BitemporalSeries.from_csv(csv_path)
    ve = VintageEnsemble(s)

    cr = ve.coverage_rate(level=0.95)
    print("=== Coverage backtest (95% CI) ===")
    print(f"  n_tested   : {cr['n_tested']}")
    print(f"  n_covered  : {cr['n_covered']}")
    print(f"  coverage   : {cr['coverage']:.3f}")
    print(f"  CI width   : [{cr['q_low']:+.2f}, {cr['q_high']:+.2f}] pp")
    print()

    # Print the fan chart for one well-revised period
    sample_period = "2017-09-01"
    hist = s.revision_history(sample_period)
    print(f"Revision history for {sample_period}:")
    print(hist.to_string(index=False))

    band = ve.uncertainty_band(sample_period)
    if band:
        print(f"\n95% CI around first release: ({band[0]:.2f}, {band[1]:.2f})")
        print(f"Final value fell {'inside' if band[0] <= s.latest(sample_period) <= band[1] else 'outside'} the band")

    # --- fig9: fan chart showing vintage progression with empirical CI ---
    # Show the 2018-2020 window: 2018 first release + CI + 2020 and 2025 vintages

    snap_2018 = s.snapshot("2018-02-02")
    snap_2020 = s.snapshot("2020-05-08")
    snap_2025 = s.snapshot("2025-07-03")
    dist = revision_distribution(s)
    q_low  = float(np.quantile(dist["deltas"], 0.025))
    q_high = float(np.quantile(dist["deltas"], 0.975))

    # Restrict to the window present in all three snapshots
    common = snap_2018.index.intersection(snap_2020.index).intersection(snap_2025.index)
    snap_2018 = snap_2018.loc[common]
    snap_2020 = snap_2020.loc[common]
    snap_2025 = snap_2025.loc[common]

    # Restrict to 2013-2018 overlap window for visual clarity
    mask = (common >= pd.Timestamp("2013-01-01")) & (common <= pd.Timestamp("2018-01-01"))
    idx  = common[mask]
    v18  = snap_2018.loc[idx]
    v20  = snap_2020.loc[idx]
    v25  = snap_2025.loc[idx]

    fig, ax = plt.subplots(figsize=(10, 5))

    # Empirical CI band around the 2018 (first-release) estimate
    ax.fill_between(
        idx, v18.values + q_low, v18.values + q_high,
        color="#cccccc", alpha=0.6, label="95% empirical CI (±0.1 pp)",
    )
    ax.plot(idx, v18.values, color="#aaaaaa", lw=1.4, ls="--", label="2018 vintage (first release)")
    ax.plot(idx, v20.values, color="#555555", lw=1.6, ls="-",  label="2020 vintage")
    ax.plot(idx, v25.values, color="#000000", lw=2.0, ls="-",  label="2025 vintage (final)")

    ax.spines["left"].set_position(("outward", 8))
    ax.spines["bottom"].set_position(("outward", 8))
    ax.set_ylim(3.5, 8.5)
    import matplotlib.dates as mdates
    ax.xaxis.set_major_locator(mdates.YearLocator(1))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    ax.set_ylabel("Unemployment rate (%)")
    ax.set_title(
        "Vintage ensemble: empirical 95% band around the 2018 first-release estimate\n"
        "All subsequent values fell within ±0.1 pp of the preliminary",
        fontsize=11, fontweight="normal", pad=14,
    )
    ax.legend(frameon=False, fontsize=9)
    fig.tight_layout()
    out = os.path.join(FIGURES, "fig9_vintage_fan.png")
    fig.savefig(out, dpi=130)
    print(f"\nwrote {os.path.relpath(out)}")
