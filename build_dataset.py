"""
build_dataset.py
================
Assemble a *real* bitemporal panel of the U.S. unemployment rate (UNRATE) from
three genuine vintages of the series, captured at different points in time.

A bitemporal observation has two clocks:

    period        -- VALID TIME:       the month the rate describes
    vintage_date  -- TRANSACTION TIME: the date that value was knowable

The three vintages below are real snapshots of FRED series UNRATE (seasonally
adjusted, monthly, BLS Current Population Survey) taken from public mirrors that
were downloaded at different times. Each file's last observation tells you
roughly when it was pulled, which we map to the corresponding BLS *Employment
Situation* release date (the first Friday after the reference month):

    _raw_vintage_2018.csv  ends 2018-01  -> vintage 2018-02-02
    _raw_vintage_2020.csv  ends 2020-04  -> vintage 2020-05-08
    _raw_vintage_2025.csv  ends 2025-06  -> vintage 2025-07-03

We also add two individually documented historical observations for January 1990
straight from the St. Louis Fed's own ALFRED example: the rate was first
reported as 5.3% on 1990-02-02 and revised to 5.4% by 1996-03-08.
(Source: https://fred.stlouisfed.org/docs/api/fred/alfred.html)

The output, data/unrate_vintages.csv, is a tidy long table:

    period, vintage_date, unrate, source

To regenerate the *full* multi-vintage panel (dozens of vintages back to 1960)
straight from the source of record, run src/fetch_vintages.py with a free FRED
API key instead. This script is the offline, fully-reproducible equivalent for
the three anchor vintages.
"""

from __future__ import annotations

import csv
import os

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "..", "data")

# (raw file, vintage_date, human-readable source)
VINTAGES = [
    ("_raw_vintage_2018.csv", "2018-02-02",
     "FRED UNRATE snapshot ending 2018-01 (BLS Jan-2018 Employment Situation)"),
    ("_raw_vintage_2020.csv", "2020-05-08",
     "FRED UNRATE snapshot ending 2020-04 (BLS Apr-2020 Employment Situation)"),
    ("_raw_vintage_2025.csv", "2025-07-03",
     "FRED UNRATE snapshot ending 2025-06 (BLS Jun-2025 Employment Situation)"),
]

# Documented historical revisions sourced directly from the ALFRED docs.
DOCUMENTED = [
    # period,      vintage_date, unrate, source
    ("1990-01-01", "1990-02-02", 5.3, "ALFRED docs: first report of Jan-1990 rate"),
    ("1990-01-01", "1996-03-08", 5.4, "ALFRED docs: revised Jan-1990 rate"),
]


def _read_vintage(path: str) -> dict[str, float]:
    """Read a 2-column (date,value) UNRATE csv regardless of header naming."""
    out: dict[str, float] = {}
    with open(path, newline="") as fh:
        reader = csv.reader(fh)
        next(reader, None)  # header
        for row in reader:
            if len(row) < 2:
                continue
            date, val = row[0].strip(), row[1].strip()
            try:
                out[date] = float(val)
            except ValueError:
                continue  # FRED writes "." for missing
    return out


def build() -> list[tuple[str, str, float, str]]:
    rows: list[tuple[str, str, float, str]] = []
    for fname, vintage_date, source in VINTAGES:
        series = _read_vintage(os.path.join(DATA, fname))
        for period, unrate in series.items():
            rows.append((period, vintage_date, unrate, source))
    rows.extend(DOCUMENTED)
    # period asc, then vintage asc -> natural bitemporal ordering
    rows.sort(key=lambda r: (r[0], r[1]))
    return rows


def main() -> None:
    rows = build()
    out_path = os.path.join(DATA, "unrate_vintages.csv")
    with open(out_path, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["period", "vintage_date", "unrate", "source"])
        w.writerows(rows)

    periods = {r[0] for r in rows}
    vintages = sorted({r[1] for r in rows})
    print(f"wrote {len(rows):,} rows -> {os.path.relpath(out_path)}")
    print(f"  distinct periods : {len(periods):,}")
    print(f"  vintages         : {', '.join(vintages)}")


if __name__ == "__main__":
    main()
