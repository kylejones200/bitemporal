"""
revision_taxonomy.py
====================
Not every revision is the same kind of news.

BLS unemployment revisions cluster by mechanism. The Seasonal Factors Revision,
published each January, re-estimates seasonal adjustment weights using five
additional years of history and revises roughly the previous 60 months of the
adjusted series. Population control updates, typically coinciding with decennial
census benchmarks and extraordinary demographic events, revise further back.
Late-arriving respondent data changes only the most recent one to three months
before the picture stabilises.

The mechanism matters because the signal-to-noise profile differs by type.
A seasonal revision to a month five years ago carries a different level of
persistence than a late-data correction to last month. If your as-of join
carries a revision_type column alongside the value, a downstream model can
treat those categories differently -- or audit the knowledge clock by checking
that seasonal revisions never touch periods outside their documented window.

Functions:
    classify_revision(series, vintage_a, vintage_b)  -- revisions + type tags
    revision_signature(series)                       -- full panel, all pairs
"""

from __future__ import annotations

import os

import pandas as pd

from bitemporal import BitemporalSeries

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
FIGURES = os.path.join(HERE, "figures")


def _lag_months(period: pd.Timestamp, knowledge_date: pd.Timestamp) -> int:
    """Calendar months between the valid-time period and the knowledge date."""
    return (
        (knowledge_date.year - period.year) * 12
        + (knowledge_date.month - period.month)
    )


def _classify(lag: int) -> str:
    """Heuristic revision type from the lag between period and knowledge date.

    BLS seasonal re-estimation touches periods up to ~60 months old.
    Anything older is a population-control or benchmark revision.
    Anything with a lag under 4 months is in the late-data window.
    """
    if lag <= 3:
        return "late_data"
    if lag <= 60:
        return "seasonal"
    return "benchmark"


def classify_revision(
    series: BitemporalSeries,
    vintage_a: str,
    vintage_b: str,
) -> pd.DataFrame:
    """Periods that revised between vintage_a and vintage_b, with type tags.

    Compares the series as known at vintage_a against the series as known at
    vintage_b and returns every period whose published value changed, annotated:

        period         -- the valid-time period that changed
        delta          -- new value minus old value (positive = revised up)
        lag_months     -- months between period and vintage_b (the knowledge date)
        revision_type  -- 'late_data', 'seasonal', or 'benchmark'

    The revision_type is the column a production system should carry alongside
    any revised value -- so a consumer can decide whether to trust, flag, or
    filter by the revision mechanism.
    """
    vintage_b_ts = pd.to_datetime(vintage_b)
    snap_a = series.snapshot(vintage_a)
    snap_b = series.snapshot(vintage_b)
    common = snap_a.index.intersection(snap_b.index)
    delta = (snap_b.loc[common] - snap_a.loc[common]).round(4)
    revised = delta[delta != 0].rename("delta").reset_index()
    revised.columns = ["period", "delta"]
    revised["lag_months"] = revised["period"].apply(
        lambda p: _lag_months(p, vintage_b_ts)
    )
    revised["revision_type"] = revised["lag_months"].apply(_classify)
    return revised.sort_values("period").reset_index(drop=True)


def revision_signature(series: BitemporalSeries) -> pd.DataFrame:
    """All revision events across the full vintage panel, with type tags.

    Iterates over consecutive vintage pairs and stacks the classify_revision
    output. The result is the dataset a revision-aware feature store would
    maintain: for every advance of the knowledge clock, here is what moved,
    by how much, and (heuristically) why.

    The vintage_pair column shows which knowledge-clock step each revision
    belongs to, so you can slice by period of time rather than by affected
    observation.
    """
    vintages = series.vintages()
    if len(vintages) < 2:
        return pd.DataFrame(
            columns=["period", "delta", "lag_months", "revision_type", "vintage_pair"]
        )
    chunks = []
    for va, vb in zip(vintages[:-1], vintages[1:]):
        chunk = classify_revision(series, str(va.date()), str(vb.date()))
        chunk["vintage_pair"] = f"{va.date()} → {vb.date()}"
        chunks.append(chunk)
    return pd.concat(chunks, ignore_index=True)


# ------------------------------------------------------------------ #
# Standalone demo + figure generation
# ------------------------------------------------------------------ #
if __name__ == "__main__":
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    csv_path = os.path.join(DATA, "unrate_vintages.csv")
    s = BitemporalSeries.from_csv(csv_path)

    sig = revision_signature(s)
    print(f"Total revision events across panel: {len(sig)}")
    print(f"\nType breakdown:\n{sig['revision_type'].value_counts().to_string()}")
    print(
        f"\nMean |delta| by type:\n"
        + sig.groupby("revision_type")["delta"]
        .apply(lambda x: x.abs().mean())
        .round(4)
        .to_string()
    )

    type_colors = {
        "late_data": "#e07b39",
        "seasonal": "#1f4e79",
        "benchmark": "#b3122f",
    }
    type_labels = {
        "late_data": "Late data (lag ≤ 3 months)",
        "seasonal": "Seasonal re-estimation (4–60 months)",
        "benchmark": "Benchmark / population control (> 60 months)",
    }

    fig, ax = plt.subplots(figsize=(10, 6))
    for rtype, grp in sig.groupby("revision_type"):
        ax.scatter(
            grp["lag_months"],
            grp["delta"].abs(),
            color=type_colors.get(rtype, "gray"),
            label=type_labels.get(rtype, rtype),
            alpha=0.75,
            s=70,
            zorder=3,
        )

    ax.set_xlabel("Lag (months between period and knowledge date)")
    ax.set_ylabel("Revision magnitude (Δ percentage points, absolute)")
    ax.set_title(
        "Revision size vs. lag by mechanism: U.S. unemployment rate\n"
        "(every revision event between three real BLS vintages)",
        fontsize=12,
    )
    ax.legend(frameon=False)
    ax.grid(True, alpha=0.25)
    fig.tight_layout()
    out = os.path.join(FIGURES, "fig5_revision_signature.png")
    fig.savefig(out, dpi=130)
    print(f"\nwrote {os.path.relpath(out)}")
