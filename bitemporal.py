"""
bitemporal.py
=============
A small, dependency-light engine for bitemporal time series.

A bitemporal fact carries two independent clocks:

    period        VALID TIME        -- when the fact is true about the world
    vintage_date  TRANSACTION TIME  -- when the fact became knowable to us

Most "time series" code silently collapses these into one, which is why
backtests leak the future and dashboards quietly rewrite history. This module
keeps both clocks explicit and gives you point-in-time-correct reads:

    series.as_of(period, knowledge_date)   # one value, as known on a date
    series.snapshot(knowledge_date)        # the whole series, as known then
    series.revision_history(period)        # how one observation changed
    series.to_scd2()                       # compact validity-interval table

The engine is generic; the bundled data happens to be U.S. unemployment.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import pandas as pd


@dataclass
class BitemporalSeries:
    """A tidy long table of (period, vintage_date, value) facts."""

    frame: pd.DataFrame  # columns: period, vintage_date, value

    # ------------------------------------------------------------------ #
    # construction
    # ------------------------------------------------------------------ #
    @classmethod
    def from_csv(
        cls,
        path: str,
        period_col: str = "period",
        vintage_col: str = "vintage_date",
        value_col: str = "unrate",
    ) -> "BitemporalSeries":
        df = pd.read_csv(path)
        out = pd.DataFrame(
            {
                "period": pd.to_datetime(df[period_col]),
                "vintage_date": pd.to_datetime(df[vintage_col]),
                "value": pd.to_numeric(df[value_col], errors="coerce"),
            }
        ).dropna(subset=["value"])
        # If a (period, vintage_date) pair repeats, keep the last one.
        out = (
            out.sort_values(["period", "vintage_date"])
            .drop_duplicates(["period", "vintage_date"], keep="last")
            .reset_index(drop=True)
        )
        return cls(out)

    # ------------------------------------------------------------------ #
    # transaction-time reads (the whole point)
    # ------------------------------------------------------------------ #
    def as_of(self, period, knowledge_date) -> Optional[float]:
        """Value for `period` as it was known on `knowledge_date`.

        Returns None if, on that date, the value had not been published yet --
        which is itself the correct, honest answer.
        """
        period = pd.to_datetime(period)
        knowledge_date = pd.to_datetime(knowledge_date)
        rows = self.frame[
            (self.frame["period"] == period)
            & (self.frame["vintage_date"] <= knowledge_date)
        ]
        if rows.empty:
            return None
        return float(rows.loc[rows["vintage_date"].idxmax(), "value"])

    def snapshot(self, knowledge_date) -> pd.Series:
        """The entire series exactly as it stood on `knowledge_date`.

        For every period, take the value carried by the latest vintage that was
        published on or before the knowledge date. Periods not yet observed on
        that date are absent -- you cannot know what you have not measured.
        """
        knowledge_date = pd.to_datetime(knowledge_date)
        visible = self.frame[self.frame["vintage_date"] <= knowledge_date]
        if visible.empty:
            return pd.Series(dtype="float64", name=str(knowledge_date.date()))
        idx = visible.groupby("period")["vintage_date"].idxmax()
        snap = (
            visible.loc[idx]
            .set_index("period")["value"]
            .sort_index()
        )
        snap.name = str(knowledge_date.date())
        return snap

    # ------------------------------------------------------------------ #
    # valid-time / revision analytics
    # ------------------------------------------------------------------ #
    def revision_history(self, period) -> pd.DataFrame:
        """Every distinct value ever carried for `period`, in knowledge order.

        Consecutive vintages that report the same number are collapsed: we only
        emit a row when the published value actually changed.
        """
        period = pd.to_datetime(period)
        rows = (
            self.frame[self.frame["period"] == period]
            .sort_values("vintage_date")
            .reset_index(drop=True)
        )
        changed = rows[rows["value"].ne(rows["value"].shift())]
        return changed[["vintage_date", "value"]].reset_index(drop=True)

    def first_release(self, period) -> Optional[float]:
        hist = self.revision_history(period)
        return None if hist.empty else float(hist.iloc[0]["value"])

    def latest(self, period) -> Optional[float]:
        hist = self.revision_history(period)
        return None if hist.empty else float(hist.iloc[-1]["value"])

    def total_revision(self, period) -> Optional[float]:
        """latest - first_release: how much the world's 'final' answer moved."""
        first, last = self.first_release(period), self.latest(period)
        if first is None or last is None:
            return None
        return round(last - first, 4)

    def revised_periods(self) -> pd.DataFrame:
        """All periods whose published value ever changed, with the delta."""
        recs = []
        for period, grp in self.frame.groupby("period"):
            vals = grp.sort_values("vintage_date")["value"]
            if vals.nunique() > 1:
                recs.append(
                    {
                        "period": period,
                        "first_release": float(vals.iloc[0]),
                        "latest": float(vals.iloc[-1]),
                        "n_revisions": int(vals.nunique() - 1),
                        "total_revision": round(
                            float(vals.iloc[-1] - vals.iloc[0]), 4
                        ),
                    }
                )
        return (
            pd.DataFrame(recs)
            .sort_values("period")
            .reset_index(drop=True)
        )

    # ------------------------------------------------------------------ #
    # compact bitemporal representation (SCD Type 2 in transaction time)
    # ------------------------------------------------------------------ #
    def to_scd2(self) -> pd.DataFrame:
        """Collapse the panel into validity intervals in transaction time.

        For each period we emit one row per *stable value*, stamped with the
        knowledge window over which that value was the official answer:

            period, value, know_from, know_to, is_current

        `know_to` is NaT for the value that is still current. This is the
        storage pattern a temporal table or a Type-2 dimension uses: write once
        per revision, never overwrite, and every past belief stays queryable.
        """
        out = []
        for period, grp in self.frame.groupby("period"):
            grp = grp.sort_values("vintage_date").reset_index(drop=True)
            changed = grp[grp["value"].ne(grp["value"].shift())].reset_index(
                drop=True
            )
            know_from = changed["vintage_date"].tolist()
            values = changed["value"].tolist()
            for i, (kf, val) in enumerate(zip(know_from, values)):
                know_to = know_from[i + 1] if i + 1 < len(know_from) else pd.NaT
                out.append(
                    {
                        "period": period,
                        "value": val,
                        "know_from": kf,
                        "know_to": know_to,
                        "is_current": pd.isna(know_to),
                    }
                )
        return (
            pd.DataFrame(out)
            .sort_values(["period", "know_from"])
            .reset_index(drop=True)
        )

    # ------------------------------------------------------------------ #
    def vintages(self) -> list[pd.Timestamp]:
        return sorted(self.frame["vintage_date"].unique())

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"BitemporalSeries(facts={len(self.frame):,}, "
            f"periods={self.frame['period'].nunique():,}, "
            f"vintages={self.frame['vintage_date'].nunique()})"
        )


# ---------------------------------------------------------------------- #
# tiny CLI so the module is runnable on its own
# ---------------------------------------------------------------------- #
if __name__ == "__main__":
    import os

    here = os.path.dirname(os.path.abspath(__file__))
    csv_path = os.path.join(here, "data", "unrate_vintages.csv")
    s = BitemporalSeries.from_csv(csv_path)
    print(s, "\n")

    # The headline: the most famous unemployment number in modern history,
    # quietly revised after the fact.
    print("April 2020, as known on 2020-06-01 :", s.as_of("2020-04-01", "2020-06-01"))
    print("April 2020, as known on 2025-12-01 :", s.as_of("2020-04-01", "2025-12-01"))
    print("April 2020 total revision          :", s.total_revision("2020-04-01"))
    print()
    print("Revision history for 2017-09:")
    print(s.revision_history("2017-09-01").to_string(index=False))
