"""
test_revision_cascade.py -- run with:  python3 -m pytest tests/ -q
                             or simply: python3 tests/test_revision_cascade.py
"""

from __future__ import annotations

import os
import sys

import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from bitemporal import BitemporalSeries
from revision_cascade import DependencyGraph, DerivedNode, SourceNode, shell_cascade


def _toy_series() -> BitemporalSeries:
    # Three vintages of the same period: 100 -> 90 -> 85
    df = pd.DataFrame(
        {
            "period": ["2000-12-31", "2000-12-31", "2000-12-31"],
            "vintage_date": ["2001-01-01", "2002-01-01", "2003-01-01"],
            "unrate": [100.0, 90.0, 85.0],
        }
    )
    df.to_csv("/tmp/_toy_cascade.csv", index=False)
    return BitemporalSeries.from_csv("/tmp/_toy_cascade.csv")


def test_source_node_respects_knowledge_date():
    s = _toy_series()
    g = DependencyGraph()
    g.add_source(SourceNode("root", s, "2000-12-31", "units"))
    assert g.value_at("root", "2001-06-01") == 100.0
    assert g.value_at("root", "2002-06-01") == 90.0
    assert g.value_at("root", "2003-06-01") == 85.0


def test_source_node_returns_none_before_first_vintage():
    s = _toy_series()
    g = DependencyGraph()
    g.add_source(SourceNode("root", s, "2000-12-31", "units"))
    assert g.value_at("root", "2000-06-01") is None


def test_derived_node_propagates_transform():
    s = _toy_series()
    g = DependencyGraph()
    g.add_source(SourceNode("root", s, "2000-12-31", "units"))
    g.add_derived(DerivedNode("doubled", parent="root", transform=lambda x: x * 2))
    assert g.value_at("doubled", "2001-06-01") == 200.0
    assert g.value_at("doubled", "2002-06-01") == 180.0


def test_chained_derived_nodes():
    s = _toy_series()
    g = DependencyGraph()
    g.add_source(SourceNode("root", s, "2000-12-31", "units"))
    g.add_derived(DerivedNode("mid", parent="root", transform=lambda x: x * 1.1))
    g.add_derived(DerivedNode("end", parent="mid", transform=lambda x: x + 5))
    # end = (100 * 1.1) + 5 = 115
    assert abs(g.value_at("end", "2001-06-01") - 115.0) < 0.01


def test_diff_cascade_captures_source_delta():
    s = _toy_series()
    g = DependencyGraph()
    g.add_source(SourceNode("root", s, "2000-12-31", "units"))
    diff = g.diff_cascade("2001-06-01", "2002-06-01")
    row = diff[diff["node"] == "root"].iloc[0]
    assert row["before"] == 100.0
    assert row["after"] == 90.0
    assert abs(row["delta"] - (-10.0)) < 1e-6


def test_diff_cascade_propagates_to_derived():
    s = _toy_series()
    g = DependencyGraph()
    g.add_source(SourceNode("root", s, "2000-12-31", "units"))
    g.add_derived(DerivedNode("scaled", parent="root", transform=lambda x: x * 2))
    diff = g.diff_cascade("2001-06-01", "2002-06-01")
    row = diff[diff["node"] == "scaled"].iloc[0]
    # root: 100 -> 90, scaled: 200 -> 180, delta = -20
    assert abs(row["delta"] - (-20.0)) < 1e-6


def test_shell_cascade_reserves_fall_after_restatement():
    g = shell_cascade()
    before = g.propagate("2003-09-01")
    after = g.propagate("2004-05-01")
    assert before["proved_reserves"] > after["proved_reserves"]


def test_shell_cascade_eur_always_exceeds_reserves():
    g = shell_cascade()
    for kd in ["2003-09-01", "2004-02-01", "2004-05-01"]:
        vals = g.propagate(kd)
        assert vals["eur"] > vals["proved_reserves"]


def test_shell_cascade_npv_moves_with_eur():
    g = shell_cascade()
    diff = g.diff_cascade("2003-09-01", "2004-05-01")
    eur_delta = diff[diff["node"] == "eur"].iloc[0]["delta"]
    npv_delta = diff[diff["node"] == "npv_usd_bn"].iloc[0]["delta"]
    # NPV = EUR * 12, so npv_delta should be ~12 * eur_delta
    assert abs(npv_delta - eur_delta * 12.0) < 0.1


def _run_all() -> None:
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"  PASS  {fn.__name__}")
    print(f"\n{len(fns)} tests passed.")


if __name__ == "__main__":
    _run_all()
