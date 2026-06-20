"""
revision_cascade.py
===================
Bitemporal correctness at the source is insufficient if downstream models do
not propagate the revision.

When Shell restated YE2002 proved reserves from 19.50 to 15.03 billion boe,
that single fact revision did not stop at the reserves line. EUR estimates fell.
NPV calculations collapsed. Reserve-replacement ratios broke their covenants.
Credit ratings moved. SEC enforcement followed. One bitemporal event cascaded
into ten downstream consequences -- because the models that consumed the
reserves figure had no way to ask "what did the source believe on *that* date
when *that* decision fired?" They read the latest number, always, and so they
could not tell the difference between a bad decision made with good information
and a good decision made with information that later turned out to be wrong.

This module implements a lightweight dependency graph for bitemporal cascades:
each node is either a BitemporalSeries (a source of facts) or a derived value
(a function of a parent node). Every node is queryable at a specific knowledge
date, so the entire graph is point-in-time correct. The key operation is
diff_cascade: given two knowledge dates, which nodes changed, and by how much?

Classes:
    SourceNode       -- leaf backed by a BitemporalSeries
    DerivedNode      -- a function of its parent's value
    DependencyGraph  -- DAG of source and derived nodes

Functions:
    shell_cascade()  -- the three-node Shell reserves chain (pre-built example)
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Callable, Optional

import pandas as pd

from bitemporal import BitemporalSeries
from reserves import load_shell_reserves

HERE = os.path.dirname(os.path.abspath(__file__))
FIGURES = os.path.join(HERE, "figures")


# ------------------------------------------------------------------ #
# Node types
# ------------------------------------------------------------------ #
@dataclass
class SourceNode:
    """A leaf node whose values come from a BitemporalSeries.

    `period` is the valid-time anchor to query. The BitemporalSeries can
    contain many periods; this node pins one of them for the cascade, so the
    graph is anchored to a single physical event (e.g., YE2002 reserves).
    """

    name: str
    series: BitemporalSeries
    period: str
    unit: str = ""

    def value_at(self, knowledge_date: str) -> Optional[float]:
        return self.series.as_of(self.period, knowledge_date)


@dataclass
class DerivedNode:
    """A node whose value is a deterministic function of its parent's value.

    When the parent revises, every derived node downstream revises too --
    automatically, because value_at is computed fresh each time. There is no
    cached result to invalidate, no pipeline to re-trigger. That simplicity
    is the point: in a correctly modelled bitemporal graph, revision
    propagation is free.
    """

    name: str
    parent: str
    transform: Callable[[float], float]
    unit: str = ""


# ------------------------------------------------------------------ #
# The graph
# ------------------------------------------------------------------ #
class DependencyGraph:
    """A lightweight DAG for bitemporal cascades.

    Add source and derived nodes, then query the entire graph at any knowledge
    date with propagate(). Use diff_cascade(date_a, date_b) to see which nodes
    changed between two knowledge dates -- and by how much.

    The order in which nodes are added is the order in which diff_cascade
    returns them, so add parents before children.
    """

    def __init__(self) -> None:
        self._sources: dict[str, SourceNode] = {}
        self._derived: dict[str, DerivedNode] = {}
        self._order: list[str] = []

    def add_source(self, node: SourceNode) -> None:
        self._sources[node.name] = node
        self._order.append(node.name)

    def add_derived(self, node: DerivedNode) -> None:
        self._derived[node.name] = node
        self._order.append(node.name)

    def value_at(self, name: str, knowledge_date: str) -> Optional[float]:
        """Compute the value of node `name` as known on `knowledge_date`."""
        if name in self._sources:
            return self._sources[name].value_at(knowledge_date)
        node = self._derived[name]
        parent_val = self.value_at(node.parent, knowledge_date)
        if parent_val is None:
            return None
        return round(node.transform(parent_val), 4)

    def propagate(self, knowledge_date: str) -> dict[str, Optional[float]]:
        """All node values as known on knowledge_date."""
        return {name: self.value_at(name, knowledge_date) for name in self._order}

    def diff_cascade(
        self, knowledge_date_a: str, knowledge_date_b: str
    ) -> pd.DataFrame:
        """Every node that changed between two knowledge dates.

        Returns a DataFrame with columns: node, unit, before, after, delta.
        Nodes that returned None at either date are excluded -- they were
        unknown at one of the two moments, which is its own useful signal but
        belongs to a different query.
        """
        va = self.propagate(knowledge_date_a)
        vb = self.propagate(knowledge_date_b)
        rows = []
        for name in self._order:
            a, b = va.get(name), vb.get(name)
            if a is None or b is None:
                continue
            unit = (
                self._sources[name].unit
                if name in self._sources
                else self._derived[name].unit
            )
            rows.append(
                {
                    "node": name,
                    "unit": unit,
                    "before": a,
                    "after": b,
                    "delta": round(b - a, 4),
                }
            )
        return pd.DataFrame(rows)


# ------------------------------------------------------------------ #
# Pre-built example: Shell YE2002 reserves chain
# ------------------------------------------------------------------ #
def shell_cascade() -> DependencyGraph:
    """Three-node cascade anchored to Shell's YE2002 proved reserves.

    proved_reserves (source) → eur → npv_usd_bn

    The transforms are simplified but structurally correct:
        EUR  = proved * 1.15  -- upward probable-to-proved conversion factor
        NPV  = EUR   * 12.0  -- simplified net economics (~$12/boe after
                                 lifting costs and a 15-year present-value
                                 discount at 2003 Brent prices)

    At $12/boe, the intent is to show the cascade structure and relative
    magnitudes, not to reproduce Shell's internal valuation. The key result
    -- that every revision to proved reserves flows proportionally through
    the chain -- holds regardless of the specific multiplier.
    """
    reserves = load_shell_reserves()
    ye2002 = BitemporalSeries(
        reserves.frame[
            reserves.frame["period"] == pd.Timestamp("2002-12-31")
        ].copy()
    )
    g = DependencyGraph()
    g.add_source(SourceNode("proved_reserves", ye2002, "2002-12-31", "bn boe"))
    g.add_derived(
        DerivedNode(
            "eur",
            parent="proved_reserves",
            transform=lambda r: r * 1.15,
            unit="bn boe",
        )
    )
    g.add_derived(
        DerivedNode(
            "npv_usd_bn",
            parent="eur",
            transform=lambda e: e * 12.0,
            unit="$bn",
        )
    )
    return g


# ------------------------------------------------------------------ #
# Standalone demo + figure generation
# ------------------------------------------------------------------ #
if __name__ == "__main__":
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    g = shell_cascade()

    before_date = "2003-09-01"   # before any restatement; 19.50 bn boe
    after_date = "2004-05-01"    # after the First Half Review; 15.03 bn boe

    diff = g.diff_cascade(before_date, after_date)
    print(f"Shell cascade diff: {before_date} → {after_date}")
    print(diff.to_string(index=False))

    # -- Figure 6: before/after comparison per node --
    node_labels = {
        "proved_reserves": "Proved Reserves\n(bn boe)",
        "eur": "EUR\n(bn boe)",
        "npv_usd_bn": "NPV\n($bn)",
    }
    colors = {
        "proved_reserves": "#1f4e79",
        "eur": "#2e75b6",
        "npv_usd_bn": "#b3122f",
    }

    fig, axes = plt.subplots(1, 3, figsize=(12, 6.5))
    for ax, (_, row) in zip(axes, diff.iterrows()):
        name = row["node"]
        ax.bar(["Before\nRestatement"], [row["before"]],
               color=colors[name], alpha=1.0, width=0.5, zorder=3)
        ax.bar(["After\nRestatement"], [row["after"]],
               color=colors[name], alpha=0.5, width=0.5, zorder=3)
        ax.set_title(node_labels.get(name, name), fontsize=11, fontweight="bold")
        ax.set_ylabel(row["unit"])
        ax.grid(True, axis="y", alpha=0.25)
        mid = (row["before"] + row["after"]) / 2
        ax.annotate(
            f"Δ {row['delta']:+.2f}",
            xy=(0.5, mid),
            xycoords=("axes fraction", "data"),
            ha="center",
            fontsize=11,
            color=colors[name],
            fontweight="bold",
        )

    fig.suptitle(
        "The cascade: Shell's 2004 restatement propagating through the model\n"
        "(proved reserves → EUR → NPV, as known on 2003-09-01 vs 2004-05-01)",
        fontsize=12,
    )
    fig.tight_layout()
    out = os.path.join(FIGURES, "fig6_cascade_waterfall.png")
    fig.savefig(out, dpi=130)
    print(f"\nwrote {os.path.relpath(out)}")
