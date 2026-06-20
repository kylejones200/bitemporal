"""
reserves.py
===========
The two clocks, ported from public economics to upstream oil & gas.

Reserves are the textbook bitemporal quantity. A proved-reserves figure is an
*estimate* attached to a fixed valid-time anchor -- "proved reserves as of
December 31, 2002" -- and that estimate moves as new information arrives, while
the anchor never does. U.S. accounting standard ASC 932-235-50 (formerly FAS 69)
makes this explicit: every reserve reconciliation must carry a line called
"Revisions of previous estimates", defined as changes to prior proved-reserve
estimates resulting from new information from development drilling, production
history, or changed economics. Revision is not error; it is information arriving
-- and the regulator mandates a column for it.

This module does two things:

  1. load_shell_reserves()  -- a REAL bitemporal panel: Royal Dutch/Shell's
     proved reserves for two fixed anchors (year-end 2002 and year-end 2003),
     restated across the documented 2004-2005 recategorisation sequence. It
     loads into the SAME BitemporalSeries engine used for unemployment, with no
     changes -- the whole point: the two clocks don't care about the domain.

  2. reconcile()            -- the ASC 932 walk-forward, the form in which the
     industry reports revisions every single year.

Data provenance for the Shell panel (all figures public, from SEC filings and
contemporaneous trade press; see data/shell_reserves_vintages.csv for per-row
sources):

  valid time 2002-12-31 (proved reserves, billion boe)
    as originally booked .................. 19.50   (2002 Annual Report)
    2004-01-09  first restatement ......... 15.60   (-3.9 bn, 20%)
    2004-03-18  second restatement ........ 15.35   (Jan+Mar -4.15 bn combined)
    2004-04-19  First Half Review done .... 15.03   (-4.474 bn total, ~23%)
  valid time 2003-12-31 (proved reserves, billion boe)
    2004-06-30  restated 2003 report ...... 14.35
    2005-02-04  Second Half Review ........ 12.95   (-1.4 bn; -5.87 bn / ~30%
                                                     vs originally-reported 2002)

The original-booking vintage_date (2003-06-30) is an approximation of the 2002
Form 20-F filing; every restatement date is the actual public announcement date.
"""

from __future__ import annotations

import os

import pandas as pd

from bitemporal import BitemporalSeries

HERE = os.path.dirname(__file__)
SHELL_CSV = os.path.join(HERE, "..", "data", "shell_reserves_vintages.csv")


# --------------------------------------------------------------------- #
# 1. Real Shell reserves, loaded into the generic bitemporal engine
# --------------------------------------------------------------------- #
def load_shell_reserves(path: str = SHELL_CSV) -> BitemporalSeries:
    """Royal Dutch/Shell proved reserves as a bitemporal series.

    Same engine as unemployment. period = the year-end the reserves describe;
    vintage_date = the date that estimate became the official answer; value =
    proved reserves in billion boe.
    """
    return BitemporalSeries.from_csv(
        path,
        period_col="period",
        vintage_col="vintage_date",
        value_col="reserves_boe_bn",
    )


# --------------------------------------------------------------------- #
# 2. The ASC 932 reconciliation walk -- revisions as a recurring flow
# --------------------------------------------------------------------- #
def reconcile(opening: float, years: list[dict]) -> pd.DataFrame:
    """Walk a proved-reserves balance forward, ASC 932 style.

    Each year dict carries the standard line items, all in the same unit:
        {"year", "revisions", "extensions", "purchases", "sales", "production"}
    Returns a tidy frame with the closing balance after each year, so the
    "revisions" column is exactly the institutionalised bitemporal signal:
    every year, prior estimates are restated as knowledge arrives.
    """
    rows = []
    balance = opening
    for y in years:
        revisions = y.get("revisions", 0.0)
        extensions = y.get("extensions", 0.0)
        purchases = y.get("purchases", 0.0)
        sales = y.get("sales", 0.0)
        production = y.get("production", 0.0)
        closing = balance + revisions + extensions + purchases + sales - production
        rows.append(
            {
                "year": y["year"],
                "opening": round(balance, 3),
                "revisions": revisions,
                "extensions": extensions,
                "purchases": purchases,
                "sales": sales,
                "production": -abs(production),
                "closing": round(closing, 3),
            }
        )
        balance = closing
    return pd.DataFrame(rows)


# A real reconciliation (oil, MBbls) from a U.S. independent's 10-K reserve
# disclosure on SEC EDGAR -- shown to make the "revisions every year" point with
# real numbers. The revisions line is positive and material in every single year.
REAL_RECONCILIATION_OIL_MBBL = [
    {"year": 2009, "revisions": 1964, "extensions": 417, "sales": -402, "production": 6207},
    {"year": 2010, "revisions": 3299, "extensions": 2668, "purchases": 637, "sales": -23, "production": 5714},
    {"year": 2011, "revisions": 2988, "extensions": 3544, "purchases": 14396, "sales": -1950, "production": 6427},
]
REAL_RECONCILIATION_OPENING_2008 = 36564  # YE2008 proved oil reserves, MBbls


# --------------------------------------------------------------------- #
if __name__ == "__main__":
    s = load_shell_reserves()

    print("=" * 64)
    print("SHELL PROVED RESERVES -- one anchor, many beliefs")
    print("=" * 64)
    print("\nWhat was 'YE2002 proved reserves' worth, asked on different dates?")
    for kd in ["2003-09-01", "2004-02-01", "2004-05-01"]:
        v = s.as_of("2002-12-31", kd)
        print(f"  as known on {kd}:  {v} bn boe")

    print("\nRevision history of the YE2002 anchor (each belief, in order):")
    print(s.revision_history("2002-12-31").to_string(index=False))

    print("\nFirst belief vs latest, and the total revision:")
    fr = s.first_release("2002-12-31")
    lt = s.latest("2002-12-31")
    print(f"  first booked {fr} bn boe  ->  latest {lt} bn boe  "
          f"({lt - fr:+.2f} bn, {(lt - fr) / fr:+.1%})")

    print("\n" + "=" * 64)
    print("ASC 932 RECONCILIATION -- revisions as a yearly flow (real 10-K, MBbls)")
    print("=" * 64)
    recon = reconcile(REAL_RECONCILIATION_OPENING_2008, REAL_RECONCILIATION_OIL_MBBL)
    print(recon.to_string(index=False))
    print(f"\nRevisions of previous estimates booked every year: "
          f"{[r['revisions'] for r in REAL_RECONCILIATION_OIL_MBBL]} MBbls. "
          f"Never zero.")
