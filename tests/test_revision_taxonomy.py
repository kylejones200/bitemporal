"""
test_revision_taxonomy.py -- run with:  python3 -m pytest tests/ -q
                              or simply: python3 tests/test_revision_taxonomy.py
"""

from __future__ import annotations

import os
import sys

import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from bitemporal import BitemporalSeries
from revision_taxonomy import classify_revision, revision_signature


def _toy() -> BitemporalSeries:
    # 2018-01: stable across both vintages (no revision)
    # 2014-04: 6.3 -> 6.2 (seasonal/benchmark revision)
    df = pd.DataFrame(
        {
            "period": [
                "2018-01-01", "2018-01-01",
                "2014-04-01", "2014-04-01",
            ],
            "vintage_date": [
                "2018-03-01", "2025-07-01",
                "2018-03-01", "2025-07-01",
            ],
            "unrate": [4.0, 4.0, 6.3, 6.2],
        }
    )
    df.to_csv("/tmp/_toy_tax.csv", index=False)
    return BitemporalSeries.from_csv("/tmp/_toy_tax.csv")


def test_classify_revision_detects_changed_periods():
    s = _toy()
    result = classify_revision(s, "2018-03-01", "2025-07-01")
    assert len(result) == 1
    assert result.iloc[0]["period"] == pd.Timestamp("2014-04-01")
    assert abs(result.iloc[0]["delta"] - (-0.1)) < 1e-6


def test_unchanged_period_is_excluded():
    s = _toy()
    result = classify_revision(s, "2018-03-01", "2025-07-01")
    periods = result["period"].tolist()
    assert pd.Timestamp("2018-01-01") not in periods


def test_classify_assigns_benchmark_for_long_lag():
    s = _toy()
    result = classify_revision(s, "2018-03-01", "2025-07-01")
    # 2014-04 revised with vintage 2025-07: lag ~134 months -> benchmark
    assert result.iloc[0]["revision_type"] == "benchmark"
    assert result.iloc[0]["lag_months"] > 60


def test_seasonal_type_for_medium_lag():
    df = pd.DataFrame(
        {
            "period": ["2019-06-01", "2019-06-01"],
            "vintage_date": ["2020-01-01", "2022-01-01"],
            "unrate": [3.6, 3.7],
        }
    )
    df.to_csv("/tmp/_toy_seasonal.csv", index=False)
    s = BitemporalSeries.from_csv("/tmp/_toy_seasonal.csv")
    result = classify_revision(s, "2020-01-01", "2022-01-01")
    # lag = (2022-01) - (2019-06) = 31 months -> seasonal
    assert len(result) == 1
    assert result.iloc[0]["revision_type"] == "seasonal"


def test_no_revision_returns_empty_frame():
    df = pd.DataFrame(
        {
            "period": ["2020-01-01", "2020-01-01"],
            "vintage_date": ["2021-01-01", "2022-01-01"],
            "unrate": [5.0, 5.0],
        }
    )
    df.to_csv("/tmp/_toy_norev.csv", index=False)
    s = BitemporalSeries.from_csv("/tmp/_toy_norev.csv")
    result = classify_revision(s, "2021-01-01", "2022-01-01")
    assert result.empty


def test_revision_signature_covers_all_vintage_pairs():
    s = _toy()
    sig = revision_signature(s)
    assert "vintage_pair" in sig.columns
    # One pair: 2018-03-01 -> 2025-07-01
    assert sig["vintage_pair"].nunique() == 1
    assert len(sig) == 1


def _run_all() -> None:
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"  PASS  {fn.__name__}")
    print(f"\n{len(fns)} tests passed.")


if __name__ == "__main__":
    _run_all()
