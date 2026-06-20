"""
revision_stats.py
=================
Statistical characterization of the revision process.

The central question: is revision random noise or structured signal?

Four functions, four angles of attack:

    revision_distribution(series)             -- mean, std, skew, Gaussian fit
    directional_bias(series)                  -- binomial test for up/down skew
    revision_autocorrelation(series, max_lag) -- Ljung-Box test on revision sequence
    confidence_band(series, knowledge_date)   -- empirical CI around current snapshot

The three-vintage UNRATE panel in this repo produces 26 revision events, all
with |delta| = 0.1pp -- the BLS reporting precision. The distribution is
discrete ({-0.1, +0.1}), not Gaussian. Every function reports that honestly.
The full FRED vintage history (ALFRED) would provide hundreds of revision events
across a continuous range and power genuine distributional tests.
"""

from __future__ import annotations

import os
from typing import Optional

import numpy as np
import pandas as pd
import scipy.stats as stats

from bitemporal import BitemporalSeries
from revision_taxonomy import revision_signature

HERE = os.path.dirname(os.path.abspath(__file__))
FIGURES = os.path.join(HERE, "figures")


def revision_distribution(series: BitemporalSeries) -> dict:
    """Descriptive statistics and Gaussian fit for all signed revision deltas.

    Returns a dict with keys: n, mean, std, skew, kurtosis,
    norm_fit_mu, norm_fit_sigma, normality_stat, normality_p, deltas (array).
    normality_stat / normality_p are NaN when n < 8 (insufficient for the test).
    """
    sig = revision_signature(series)
    if sig.empty:
        return {}
    deltas = sig["delta"].dropna().values
    n = len(deltas)
    mu, sigma = stats.norm.fit(deltas)
    if n >= 8:
        norm_stat, norm_p = stats.normaltest(deltas)
    else:
        norm_stat, norm_p = float("nan"), float("nan")
    return {
        "n": n,
        "mean": float(np.mean(deltas)),
        "std": float(np.std(deltas)),
        "skew": float(stats.skew(deltas)),
        "kurtosis": float(stats.kurtosis(deltas)),
        "norm_fit_mu": float(mu),
        "norm_fit_sigma": float(sigma),
        "normality_stat": float(norm_stat),
        "normality_p": float(norm_p),
        "deltas": deltas,
    }


def directional_bias(series: BitemporalSeries) -> dict:
    """Two-sided binomial test: are revisions more likely to be positive or negative?

    Zeros (unchanged values) are excluded from the test because only non-zero
    revisions carry directional information. Returns n_positive, n_negative,
    fraction_positive, p_value, and bias_direction.
    """
    sig = revision_signature(series)
    if sig.empty:
        return {}
    deltas = sig["delta"].dropna()
    n_pos = int((deltas > 0).sum())
    n_neg = int((deltas < 0).sum())
    n_zero = int((deltas == 0).sum())
    n_total = n_pos + n_neg
    if n_total == 0:
        return {"n_positive": 0, "n_negative": 0, "n_zero": n_zero,
                "fraction_positive": float("nan"), "p_value": float("nan"),
                "statistic": float("nan"), "bias_direction": "none"}
    result = stats.binomtest(n_pos, n_total, p=0.5, alternative="two-sided")
    return {
        "n_positive": n_pos,
        "n_negative": n_neg,
        "n_zero": n_zero,
        "fraction_positive": n_pos / n_total,
        "p_value": float(result.pvalue),
        "statistic": float(result.statistic),
        "bias_direction": (
            "positive" if n_pos > n_neg else
            "negative" if n_neg > n_pos else
            "none"
        ),
    }


def revision_autocorrelation(
    series: BitemporalSeries,
    max_lag: int = 5,
) -> pd.DataFrame:
    """Ljung-Box test for autocorrelation in the period-ordered revision sequence.

    Returns a DataFrame indexed by lag with columns lb_stat and lb_pvalue.
    An empty DataFrame is returned if there are too few observations.
    max_lag is capped at n//4 to keep degrees of freedom sensible.
    """
    from statsmodels.stats.diagnostic import acorr_ljungbox

    sig = revision_signature(series)
    if sig.empty:
        return pd.DataFrame()
    deltas = sig.sort_values("period")["delta"].values
    n = len(deltas)
    effective_max = min(max_lag, max(1, n // 4))
    if n < effective_max + 2:
        return pd.DataFrame()
    lags = list(range(1, effective_max + 1))
    return acorr_ljungbox(deltas, lags=lags, return_df=True)


def confidence_band(
    series: BitemporalSeries,
    knowledge_date: str,
    level: float = 0.95,
) -> pd.DataFrame:
    """Empirical CI around every value in the current snapshot.

    The interval is derived from the empirical quantiles of the full revision
    distribution: if a preliminary value v₀ eventually becomes v_final, and
    the historical distribution of (v_final - v₀) has q_low at the α/2 quantile
    and q_high at the (1-α/2) quantile, then [v₀ + q_low, v₀ + q_high] is the
    empirical confidence interval.

    Returns: period, point_estimate, lower, upper, q_low, q_high, level.
    """
    dist = revision_distribution(series)
    if not dist:
        return pd.DataFrame()
    deltas = dist["deltas"]
    alpha = 1 - level
    q_low = float(np.quantile(deltas, alpha / 2))
    q_high = float(np.quantile(deltas, 1 - alpha / 2))
    snap = series.snapshot(knowledge_date)
    return pd.DataFrame({
        "period":         snap.index,
        "point_estimate": snap.values,
        "lower":          snap.values + q_low,
        "upper":          snap.values + q_high,
        "q_low":          q_low,
        "q_high":         q_high,
        "level":          level,
    })


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

    dist = revision_distribution(s)
    bias = directional_bias(s)
    acf  = revision_autocorrelation(s)

    print("=== Revision distribution ===")
    print(f"  n           : {dist['n']}")
    print(f"  mean        : {dist['mean']:+.4f} pp")
    print(f"  std         : {dist['std']:.4f} pp")
    print(f"  skew        : {dist['skew']:.4f}")
    print(f"  kurtosis    : {dist['kurtosis']:.4f}")
    print(f"  Gaussian fit: μ={dist['norm_fit_mu']:+.4f}, σ={dist['norm_fit_sigma']:.4f}")
    print(f"  Normality   : stat={dist['normality_stat']:.3f}, p={dist['normality_p']:.4f}")
    print()
    print("=== Directional bias ===")
    print(f"  n_positive        : {bias['n_positive']}")
    print(f"  n_negative        : {bias['n_negative']}")
    print(f"  fraction positive : {bias['fraction_positive']:.3f}")
    print(f"  binomial p-value  : {bias['p_value']:.4f}")
    print(f"  bias direction    : {bias['bias_direction']}")
    print()
    print("=== Ljung-Box autocorrelation ===")
    if not acf.empty:
        print(acf.round(4).to_string())
    else:
        print("  (insufficient observations)")

    # --- fig8: histogram of revision deltas with Gaussian overlay ---
    deltas = dist["deltas"]

    fig, ax = plt.subplots(figsize=(9, 5))

    # For a discrete distribution {-0.1, +0.1}, draw a true histogram
    # with one bar per value and color code by direction.
    n_neg = (deltas < 0).sum()
    n_pos = (deltas > 0).sum()
    ax.bar([-0.1], [n_neg], width=0.04, color="black",  label=f"Downward ({n_neg})")
    ax.bar([+0.1], [n_pos], width=0.04, color="#888888", label=f"Upward ({n_pos})")

    # Gaussian overlay (scaled to match bar heights)
    x = np.linspace(-0.25, 0.25, 300)
    pdf = stats.norm.pdf(x, dist["norm_fit_mu"], dist["norm_fit_sigma"])
    scale = dist["n"] * 0.04          # bar_width × n gives roughly correct area
    ax.plot(x, pdf * scale, color="#444444", lw=1.5, ls="--",
            label=f"Gaussian fit (μ={dist['norm_fit_mu']:+.3f}, σ={dist['norm_fit_sigma']:.3f})")

    p_str = f"p = {bias['p_value']:.3f}" if bias["p_value"] < 0.999 else "p > 0.999"
    ax.text(0.97, 0.95,
            f"Directional bias test\n{p_str}  (n = {bias['n_positive']+bias['n_negative']})",
            transform=ax.transAxes, ha="right", va="top",
            fontsize=9, color="#444444")

    ax.spines["left"].set_position(("outward", 8))
    ax.spines["bottom"].set_position(("outward", 8))
    ax.set_xlabel("Revision delta (percentage points)")
    ax.set_ylabel("Count")
    ax.set_xlim(-0.25, 0.25)
    ax.set_title(
        "Revision distribution: U.S. unemployment rate (5-vintage panel)\n"
        "All revisions lie at ±0.1 pp — the BLS reporting precision boundary",
        fontsize=11, fontweight="normal", pad=14,
    )
    ax.legend(frameon=False, fontsize=9)
    fig.tight_layout()
    out = os.path.join(FIGURES, "fig8_revision_distribution.png")
    fig.savefig(out, dpi=130)
    print(f"\nwrote {os.path.relpath(out)}")
