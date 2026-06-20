"""
test_bitemporal_duckdb.py -- run with:  python3 -m pytest tests/ -q
                              or simply: python3 tests/test_bitemporal_duckdb.py
"""

from __future__ import annotations

import os
import sys

import duckdb
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from bitemporal_duckdb import (
    asof_query,
    create_bitemporal_table,
    generate_well_production,
)


def _small() -> pd.DataFrame:
    return generate_well_production(n_wells=5, n_months=6, n_vintages=2)


def test_generate_shape():
    df = _small()
    assert len(df) == 5 * 6 * 2
    assert set(df.columns) == {"api", "period", "vintage_date", "production_boe"}
    assert (df["production_boe"] >= 0).all()


def test_asof_returns_empty_before_any_vintage():
    df = _small()
    conn = duckdb.connect()
    create_bitemporal_table(conn, "facts", df)
    result = asof_query(conn, "facts", "2020-01-01")
    assert len(result) == 0
    conn.close()


def test_asof_returns_all_rows_after_first_vintage():
    df = _small()
    conn = duckdb.connect()
    create_bitemporal_table(conn, "facts", df)
    # First vintage is 2021-01-01
    result = asof_query(conn, "facts", "2021-06-01")
    assert len(result) == 5 * 6
    conn.close()


def test_asof_returns_latest_available_vintage():
    df = pd.DataFrame(
        {
            "api": ["test_well"] * 3,
            "period": pd.to_datetime(["2021-01-01"] * 3),
            "vintage_date": pd.to_datetime(
                ["2021-02-01", "2022-02-01", "2023-02-01"]
            ),
            "production_boe": [1000.0, 1010.0, 1020.0],
        }
    )
    conn = duckdb.connect()
    create_bitemporal_table(conn, "facts", df)

    # Knowledge date 2022-06-01 -> should see the 2022-02-01 vintage
    result = asof_query(conn, "facts", "2022-06-01")
    assert len(result) == 1
    assert result.iloc[0]["production_boe"] == 1010.0

    # Knowledge date 2023-06-01 -> should see the 2023-02-01 vintage
    result2 = asof_query(conn, "facts", "2023-06-01")
    assert result2.iloc[0]["production_boe"] == 1020.0
    conn.close()


def test_asof_excludes_future_vintages():
    df = pd.DataFrame(
        {
            "api": ["w1"] * 2,
            "period": pd.to_datetime(["2021-01-01"] * 2),
            "vintage_date": pd.to_datetime(["2022-01-01", "2024-01-01"]),
            "production_boe": [500.0, 520.0],
        }
    )
    conn = duckdb.connect()
    create_bitemporal_table(conn, "facts", df)
    # Knowledge date before the second vintage should return the first
    result = asof_query(conn, "facts", "2023-01-01")
    assert len(result) == 1
    assert result.iloc[0]["production_boe"] == 500.0
    conn.close()


def test_create_table_idempotent():
    df = _small()
    conn = duckdb.connect()
    create_bitemporal_table(conn, "facts", df)
    create_bitemporal_table(conn, "facts", df)  # CREATE OR REPLACE -- should not raise
    result = asof_query(conn, "facts", "2021-06-01")
    assert len(result) == 5 * 6
    conn.close()


def _run_all() -> None:
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"  PASS  {fn.__name__}")
    print(f"\n{len(fns)} tests passed.")


if __name__ == "__main__":
    _run_all()
