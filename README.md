# bitemporal-time-series

**Data with two clocks — and the code to query it honestly.**

A small, dependency-light engine for **bitemporal time series**: data that tracks not just *when something was true* (valid time) but *when you knew it* (transaction time). Built on **real U.S. unemployment vintages**, with a working as-of backtester, the Sahm recession indicator, tests, and a live FRED fetcher.

This repo accompanies a three-part Medium series:

1. **[The Two Clocks: A Field Guide to Bitemporal Time Series](./articles/the-two-clocks-bitemporal-time-series.md)** — valid vs. transaction time, why April 2020 unemployment is *both* 14.7% and 14.8%, and a `BitemporalSeries` engine that can reconstruct what anyone knew on any past date.
2. **[Backtesting Without Cheating: Bitemporal Joins, As-Of Correctness, and the Sahm Rule](./articles/backtesting-without-cheating-bitemporal-asof.md)** — how look-ahead bias leaks into every naive backtest, how to measure the leak, and how to store two clocks append-only (SCD2).
3. **[Reserves Have Two Clocks: How Shell Lost 30% of Its Barrels Without Pumping Them](./articles/reserves-have-two-clocks-bitemporal-wells.md)** — the two clocks ported to upstream oil & gas: the real Shell reserves restatement, the ASC 932 "revisions of previous estimates" mandate, and why decisions-as-code in the subsurface demand data-as-of.

---

## The one idea

> An observation is not "the unemployment rate in April 2020." It is "the unemployment rate **for** April 2020 **as known on** a particular date."

Store both clocks and "what did we know then?" becomes a one-line lookup instead of an archaeology project.

---

## Repo layout

```
bitemporal-time-series/
├── src/
│   ├── bitemporal.py        # BitemporalSeries: as_of, snapshot, revision_history, to_scd2, ...
│   ├── asof_backtest.py     # asof_join (with leak column), sahm_trigger, compare_vintages
│   ├── reserves.py          # ports the engine to oil & gas: real Shell reserves + ASC 932 reconciliation
│   ├── build_dataset.py     # assembles the real bitemporal panel from 3 vintages + 1990 anchor
│   ├── fetch_vintages.py    # live FRED downloader: pandas_datareader (current) + keyed/keyless vintages
│   └── test_bitemporal.py   # 5 unit tests, no external deps
├── data/
│   ├── unrate_vintages.csv          # tidy panel: period, vintage_date, unrate, source
│   ├── unrate_bitemporal_scd2.csv   # same facts as validity intervals (SCD2)
│   ├── shell_reserves_vintages.csv  # real Shell proved-reserves restatement (two anchors, many vintages)
│   └── _raw_vintage_*.csv           # the three raw mirror snapshots
├── figures/                 # fan-of-vintages, revision deltas, series + Sahm triggers, Shell restatement
├── requirements.txt
└── README.md
```

---

## Data provenance (read this — it's honest)

The headline numbers are **real**. The vintage *dates* are an honest, documented approximation. Here's exactly how the panel was built:

- **Three real vintages** of FRED series `UNRATE` (seasonally adjusted, monthly, from the BLS Current Population Survey) were captured from public GitHub mirrors that had each downloaded the series at a different time. The last observation in each file tells you roughly when it was pulled, which is mapped to the corresponding BLS *Employment Situation* release date:

  | Raw file | Series ends | Attributed vintage_date |
  |---|---|---|
  | `_raw_vintage_2018.csv` | 2018-01 | 2018-02-02 |
  | `_raw_vintage_2020.csv` | 2020-04 (=14.7) | 2020-05-08 |
  | `_raw_vintage_2025.csv` | 2025-06 | 2025-07-03 |

- Diffing the three vintages surfaces **26 genuinely revised months**, all ±0.1pp, clustered 2014–2020 — the seasonal-adjustment re-estimation signature. Including the famous **April 2020: 14.7 → 14.8**.
- **Two historical anchor observations** for January 1990 come straight from the St. Louis Fed's own ALFRED example: first reported 5.3% on 1990-02-02, revised to 5.4% by 1996-03-08. Source: https://fred.stlouisfed.org/docs/api/fred/alfred.html

**Want the full, exact panel?** `src/fetch_vintages.py` pulls the complete revision history (dozens of vintages, single-month resolution) directly from FRED, where each observation arrives as a real bitemporal tuple `(date, realtime_start, realtime_end, value)`. Free API key: https://fred.stlouisfed.org/docs/api/api_key.html — a keyless CSV path is included too.

### Oil & gas: the Shell reserves panel (Article 3)

`data/shell_reserves_vintages.csv` is a **real** bitemporal panel: Royal Dutch/Shell's proved reserves for two fixed valid-time anchors (year-end 2002 and year-end 2003), restated across the documented 2004–2005 recategorisation sequence. Figures are public, from SEC filings (Forms 20-F/A and 6-K) and contemporaneous trade press; per-row sources are in the CSV. The originally-booked vintage date (2003-06-30) approximates the 2002 Form 20-F filing; every restatement date is the actual public announcement date.

```python
from src.reserves import load_shell_reserves

r = load_shell_reserves()
r.as_of("2002-12-31", "2003-09-01")   # 19.50 bn boe — what the market believed
r.as_of("2002-12-31", "2004-05-01")   # 15.03 bn boe — after the First Half Review
r.total_revision("2002-12-31")         # -4.47 bn boe (-22.9%)
```

It loads into the **same** `BitemporalSeries` engine as unemployment, with nothing but a different `value_col` — which is the whole point of Article 3.

---

## Quickstart

```bash
pip install -r requirements.txt

# rebuild the bitemporal panel from the raw vintages (writes data/unrate_vintages.csv)
python src/build_dataset.py

# run the as-of backtest demo: leak column + Sahm trigger on real data
python src/asof_backtest.py

# run the oil & gas port: real Shell reserves restatement + ASC 932 reconciliation
python src/reserves.py

# tests (no pytest needed)
python src/test_bitemporal.py
```

Core usage:

```python
from src.bitemporal import BitemporalSeries

s = BitemporalSeries.from_csv("data/unrate_vintages.csv")

s.as_of("2020-04-01", "2020-06-01")   # 14.7  — what you knew in June 2020
s.as_of("2020-04-01", "2025-12-01")   # 14.8  — what you know today
s.revision_history("2020-04-01")       # every belief about April 2020, in order
s.to_scd2()                            # validity intervals, append-only
```

---

## Pull the live data yourself

The cleanest pull of the **current** series is `pandas_datareader` — one line, no key:

```python
import pandas_datareader.data as web
unrate = web.DataReader("UNRATE", "fred", "1948-01-01")   # latest vintage only
```

But that returns the *latest* revision only — under the hood it requests `fredgraph.csv?id=UNRATE` with no vintage parameter. For the **bitemporal** history (the point of this repo) use the keyed API, which returns every revision in one call:

```python
from src.fetch_vintages import fetch_current, fetch_vintages_api

latest = fetch_current("UNRATE")                              # easy, current only
full   = fetch_vintages_api("UNRATE", api_key="YOUR_FREE_FRED_KEY")
# full.columns: period, vintage_date, value  -> drop straight into BitemporalSeries
```

A keyless route (`fetch_vintages_keyless`) hits the same public CSV endpoint as `pandas_datareader` but adds the `&vintage_date=` parameter it omits, one snapshot at a time — handy if you'd rather not register.

---

## License / data notes

Code is provided as-is for illustration. Unemployment data originates from the U.S. Bureau of Labor Statistics via the Federal Reserve Bank of St. Louis (FRED/ALFRED); see FRED's terms for the underlying series. The raw mirror snapshots are included only to make the examples reproducible offline.
