"""
asof_backtest.py
================
Why bitemporal correctness is not academic: the same rule, evaluated against
"the data as it exists today" versus "the data as it existed at decision time,"
can give different answers. The first number is a backtest. The second is what
would actually have happened. Only the second one is allowed to be optimistic.

This module provides:

    asof_join(decisions, series)   -- a point-in-time-correct as-of join
    sahm_trigger(level_series)     -- the Sahm recession indicator
    compare_vintages(series, ...)  -- run a signal on revised vs as-known data

The Sahm Rule (Claudia Sahm, 2019): a recession signal fires when the 3-month
moving average of the unemployment rate rises at least 0.50 percentage points
above its low over the prior 12 months. It is a clean test case because it is
defined on the very series that gets revised, so the trigger month can move
when the underlying numbers are revised after the fact.
"""

from __future__ import annotations

import pandas as pd

from bitemporal import BitemporalSeries


# --------------------------------------------------------------------- #
# 1. The as-of join: attach each decision the value it could have seen
# --------------------------------------------------------------------- #
def asof_join(decisions: pd.DataFrame, series: BitemporalSeries) -> pd.DataFrame:
    """Point-in-time join.

    `decisions` has columns [decision_date, period]. For each row we attach:
        known_value  -- series.as_of(period, decision_date)  (no look-ahead)
        latest_value -- the value we would read today        (look-ahead)
        leak         -- latest_value - known_value           (the bias)
    """
    out = decisions.copy()
    known, latest = [], []
    for _, row in out.iterrows():
        known.append(series.as_of(row["period"], row["decision_date"]))
        latest.append(series.latest(row["period"]))
    out["known_value"] = known
    out["latest_value"] = latest
    out["leak"] = [
        None if k is None or l is None else round(l - k, 4)
        for k, l in zip(known, latest)
    ]
    return out


# --------------------------------------------------------------------- #
# 2. The signal under test
# --------------------------------------------------------------------- #
def sahm_trigger(level: pd.Series) -> pd.DataFrame:
    """Compute the Sahm recession indicator from a monthly UNRATE series.

    Returns a frame indexed by period with the 3-month average, the trailing
    12-month low of that average, the gap, and a boolean `triggered`.
    """
    level = level.sort_index()
    ma3 = level.rolling(3).mean()
    low12 = ma3.rolling(12).min()
    gap = (ma3 - low12).round(2)
    return pd.DataFrame(
        {"ma3": ma3.round(3), "low12": low12.round(3), "gap": gap,
         "triggered": gap >= 0.50}
    )


# --------------------------------------------------------------------- #
# 3. Revised-vs-as-known comparison
# --------------------------------------------------------------------- #
def compare_vintages(
    series: BitemporalSeries,
    early_vintage: str,
    late_vintage: str,
) -> pd.DataFrame:
    """Run the Sahm trigger on two snapshots and surface the months that flip."""
    early = series.snapshot(early_vintage)
    late = series.snapshot(late_vintage)

    se = sahm_trigger(early)["triggered"]
    sl = sahm_trigger(late)["triggered"]

    joined = pd.DataFrame({"as_known": se, "revised": sl}).dropna()
    flips = joined[joined["as_known"] != joined["revised"]]
    return flips


def _demo() -> None:
    import os

    here = os.path.dirname(os.path.abspath(__file__))
    csv_path = os.path.join(here, "data", "unrate_vintages.csv")
    s = BitemporalSeries.from_csv(csv_path)

    print("=" * 64)
    print("1. AS-OF JOIN: the same questions, asked at different times")
    print("=" * 64)
    decisions = pd.DataFrame(
        {
            # An analyst standing on each date, asking about a recent month.
            "decision_date": ["2018-03-01", "2020-06-01", "2025-12-01"],
            "period": ["2017-09-01", "2020-04-01", "2017-09-01"],
        }
    )
    joined = asof_join(decisions, s)
    print(joined.to_string(index=False))
    print(
        "\nThe 2017-09 rate was 4.2 to anyone asking in 2018, but 4.3 to anyone\n"
        "asking today. A backtest that uses 4.3 for a 2018 decision is cheating."
    )

    print("\n" + "=" * 64)
    print("2. REVISED vs AS-KNOWN: does the Sahm signal move under revision?")
    print("=" * 64)
    flips = compare_vintages(s, "2020-05-08", "2025-07-03")
    if flips.empty:
        print("No Sahm-trigger month flips between these two vintages on the")
        print("overlapping window -- the revisions are real but sub-threshold here.")
        print("(With the full monthly FRED vintage panel, borderline triggers do")
        print(" flip; see fetch_vintages.py to reproduce at full resolution.)")
    else:
        print(flips.to_string())

    print("\n" + "=" * 64)
    print("3. The signal itself, on the latest real series")
    print("=" * 64)
    latest = s.snapshot("2025-07-03")
    sahm = sahm_trigger(latest)
    fired = sahm[sahm["triggered"]]
    print(f"Months the Sahm rule fired (latest vintage): {len(fired)}")
    print("Most recent firing window:")
    print(fired.tail(3).to_string())


if __name__ == "__main__":
    _demo()
