"""
bitemporal_duckdb.py
====================
From pedagogical to production: DuckDB as a bitemporal engine at scale.

BitemporalSeries.as_of() is O(n) per period -- it scans the full panel for
every query. For a single 900-month unemployment series, that is fine.
For a production well estate -- 50,000 wells, 30 years of monthly production,
10 vintage dates -- you are running 18 million row-scans per query, and you
will not ship this.

DuckDB's vectorised window functions implement the same as-of semantics in a
single SQL pass. The query is identical in semantics to snapshot() and as_of():
for every (api, period) pair, find the most recent vintage that is on or before
the knowledge date and return that value. DuckDB does it with sorted partitions
and a parallel radix join. The pandas approach does it with a Python loop.

This module shows:

    generate_well_production(n_wells)     -- synthetic but realistic panel
    create_bitemporal_table(conn, name)   -- load into DuckDB
    asof_query(conn, table, date)         -- point-in-time snapshot in SQL
    benchmark_naive_vs_duckdb(sizes)      -- timing comparison across scales

Schema convention for any production bitemporal fact table:

    period          DATE    -- VALID TIME: the date the fact describes
    vintage_date    DATE    -- TRANSACTION TIME: when the fact became known
    [value columns]         -- whatever the domain demands

Both columns present, both clocks explicit. The as-of query is then always
the same shape: `WHERE vintage_date <= :knowledge_date`, partition by the
identity key, `ORDER BY vintage_date DESC`, take row 1.
"""

from __future__ import annotations

import os
import time
from typing import Sequence

import duckdb
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
FIGURES = os.path.join(HERE, "figures")


# ------------------------------------------------------------------ #
# Synthetic well production panel
# ------------------------------------------------------------------ #
def generate_well_production(
    n_wells: int,
    n_months: int = 24,
    n_vintages: int = 3,
    seed: int = 42,
) -> pd.DataFrame:
    """Simulate a bitemporal production panel for n_wells.

    Initial production (IP) follows a log-normal distribution calibrated to
    U.S. unconventional operators (~540 BOE/day median). Decline is Arps
    hyperbolic with b=0.8 and 8% initial monthly rate. Each vintage introduces
    small uncorrelated revisions drawn from N(0, 1.5%), compounding with
    vintage index -- so the third vintage differs from the first by ~3%.

    Returns a tidy long table: api, period, vintage_date, production_boe.
    Row count = n_wells × n_months × n_vintages.
    """
    rng = np.random.default_rng(seed)
    vintage_dates = pd.to_datetime(
        ["2021-01-01", "2022-01-01", "2023-01-01"]
    )[:n_vintages]
    periods = pd.date_range("2018-01", periods=n_months, freq="MS")

    rows = []
    for i in range(n_wells):
        api = f"42{i:09d}"
        ip = float(rng.lognormal(6.3, 0.7))
        b, di = 0.8, 0.08
        base = np.array(
            [ip / (1 + b * di * m) ** (1 / b) for m in range(n_months)]
        )
        for v_idx, vintage in enumerate(vintage_dates):
            noise = 1.0 + rng.normal(0, 0.015) * v_idx
            values = np.maximum(0, base * noise).round(1)
            for period, val in zip(periods, values):
                rows.append(
                    {
                        "api": api,
                        "period": period,
                        "vintage_date": vintage,
                        "production_boe": val,
                    }
                )
    return pd.DataFrame(rows)


# ------------------------------------------------------------------ #
# DuckDB table creation and as-of query
# ------------------------------------------------------------------ #
def create_bitemporal_table(
    conn: duckdb.DuckDBPyConnection, name: str, df: pd.DataFrame
) -> None:
    """Load a pandas panel into DuckDB with the two-clock schema."""
    conn.execute(
        f"""
        CREATE OR REPLACE TABLE {name} AS
        SELECT
            api,
            period::DATE       AS period,
            vintage_date::DATE AS vintage_date,
            production_boe
        FROM df
        ORDER BY api, period, vintage_date
        """
    )


def asof_query(
    conn: duckdb.DuckDBPyConnection,
    table: str,
    knowledge_date: str,
) -> pd.DataFrame:
    """Point-in-time snapshot: the full panel as known on knowledge_date.

    For every (api, period) pair, returns the value carried by the most recent
    vintage published on or before knowledge_date. This is snapshot() from
    BitemporalSeries, expressed in SQL and executed by DuckDB's vectorised
    window engine.

    The two-clock invariant: period is the world clock (what the fact
    describes); vintage_date is the knowledge clock (when we learned it).
    The WHERE clause gates on the knowledge clock; the ROW_NUMBER orders within
    each world-clock bucket to select the most recent surviving belief.
    """
    return conn.execute(
        f"""
        WITH ranked AS (
            SELECT
                api,
                period,
                vintage_date,
                production_boe,
                ROW_NUMBER() OVER (
                    PARTITION BY api, period
                    ORDER BY vintage_date DESC
                ) AS rn
            FROM {table}
            WHERE vintage_date <= DATE '{knowledge_date}'
        )
        SELECT api, period, vintage_date, production_boe
        FROM ranked
        WHERE rn = 1
        ORDER BY api, period
        """
    ).df()


# ------------------------------------------------------------------ #
# Benchmark: pandas loop vs DuckDB
# ------------------------------------------------------------------ #
def _pandas_asof(df: pd.DataFrame, knowledge_date: str) -> pd.DataFrame:
    """The pandas baseline: filter, group, idxmax -- O(n) per partition."""
    kd = pd.to_datetime(knowledge_date)
    visible = df[df["vintage_date"] <= kd]
    idx = visible.groupby(["api", "period"])["vintage_date"].idxmax()
    return visible.loc[idx].reset_index(drop=True)


def benchmark_naive_vs_duckdb(
    sizes: Sequence[int] = (200, 1_000, 5_000, 20_000),
    knowledge_date: str = "2022-06-01",
) -> pd.DataFrame:
    """Time pandas vs DuckDB across a range of panel sizes (n_wells).

    Returns a DataFrame with n_wells, n_rows, pandas_s, duckdb_s, speedup.
    Each size is run once; for publication-quality results run several times
    and take the median.
    """
    results = []
    for n_wells in sizes:
        df = generate_well_production(n_wells)
        n_rows = len(df)

        t0 = time.perf_counter()
        _pandas_asof(df, knowledge_date)
        pandas_s = time.perf_counter() - t0

        conn = duckdb.connect()
        create_bitemporal_table(conn, "facts", df)
        t0 = time.perf_counter()
        asof_query(conn, "facts", knowledge_date)
        duckdb_s = time.perf_counter() - t0
        conn.close()

        results.append(
            {
                "n_wells": n_wells,
                "n_rows": n_rows,
                "pandas_s": round(pandas_s, 4),
                "duckdb_s": round(duckdb_s, 4),
                "speedup": round(pandas_s / max(duckdb_s, 1e-6), 1),
            }
        )
        print(
            f"  {n_wells:>6} wells  {n_rows:>8,} rows  "
            f"pandas {pandas_s:.3f}s  duckdb {duckdb_s:.3f}s  "
            f"×{pandas_s / max(duckdb_s, 1e-6):.1f}"
        )
    return pd.DataFrame(results)


# ------------------------------------------------------------------ #
if __name__ == "__main__":
    import matplotlib as mpl
    import matplotlib.pyplot as plt
    mpl.use("Agg")
    mpl.rcParams.update({"font.family": "serif", "axes.grid": False,
                         "axes.spines.top": False, "axes.spines.right": False})

    print("Benchmarking pandas vs DuckDB bitemporal as-of join...\n")
    results = benchmark_naive_vs_duckdb(sizes=[200, 1_000, 5_000, 20_000, 75_000])

    fig, ax = plt.subplots(figsize=(10, 5))
    ax.loglog(results["n_rows"], results["pandas_s"],
              "o-",  color="black",   lw=1.8, ms=5, label="pandas groupby + idxmax")
    ax.loglog(results["n_rows"], results["duckdb_s"],
              "s--", color="#777777", lw=1.8, ms=5, label="DuckDB vectorised window")

    for _, row in results.iterrows():
        if row["speedup"] >= 1.5:
            ax.annotate(f"×{row['speedup']:.0f}",
                        xy=(row["n_rows"], row["pandas_s"]),
                        xytext=(0, 9), textcoords="offset points",
                        ha="center", fontsize=8.5, color="#444444")

    ax.spines["left"].set_position(("outward", 8))
    ax.spines["bottom"].set_position(("outward", 8))
    ax.set_xlabel("Rows in the bitemporal panel (log scale)")
    ax.set_ylabel("As-of query time, seconds (log scale)")
    ax.set_title("Bitemporal as-of join: pandas vs DuckDB\n"
                 "(synthetic well production, 24 months × 3 vintages per well)",
                 fontsize=11, fontweight="normal", pad=14)
    ax.legend(frameon=False, fontsize=9)
    fig.tight_layout()
    out = os.path.join(FIGURES, "fig7_scale_benchmark.png")
    fig.savefig(out, dpi=130)
    print(f"\nwrote {os.path.relpath(out)}")
    print("\nFull results:")
    print(results.to_string(index=False))
