"""
fetch_vintages.py
=================
Pull *real* data straight from the source of record: FRED / ALFRED at the
St. Louis Fed. Three paths, in order of how you'll usually reach for them.

0) fetch_current  -- the cleanest way to pull a series, via pandas_datareader:
       import pandas_datareader.data as web
       web.DataReader("UNRATE", "fred", start, end)
   One line, no API key, returns a tidy DataFrame. IMPORTANT for this repo:
   pandas_datareader's FRED reader requests `fredgraph.csv?id=<series>` and
   passes *no* realtime/vintage parameters, so it returns the LATEST VINTAGE
   ONLY. It is perfect for "give me the current series" and useless for "give
   me what was known on date X." For the bitemporal history you need (A) or (B).

A) fetch_vintages_api  -- the canonical bitemporal route. Needs a free FRED API
   key (https://fred.stlouisfed.org/docs/api/api_key.html). One request returns
   the entire revision history as (date, realtime_start, realtime_end, value)
   tuples -- exactly a bitemporal panel: `value` was the believed number for
   `date` during the knowledge window [realtime_start, realtime_end].

B) fetch_vintages_keyless -- no key required. Hits the same public fredgraph CSV
   endpoint as pandas_datareader, but adds the `&vintage_date=` parameter that
   pandas_datareader omits, once per vintage date you ask for. Slower and
   coarser, but needs no credentials.

All bitemporal paths return a tidy DataFrame [period, vintage_date, value] that
drops straight into bitemporal.BitemporalSeries.

    df = fetch_vintages_api("UNRATE", api_key=os.environ["FRED_API_KEY"])
    df.to_csv("data/unrate_vintages_full.csv", index=False)

Note: install with `pip install pandas_datareader`. Some pandas_datareader
releases break on import against very recent pandas (a `deprecate_kwarg`
TypeError); if you hit it, pin a compatible pandas or use path (B), which only
needs `requests`.
"""

from __future__ import annotations

import io
import os

import pandas as pd
import requests


# --------------------------------------------------------------------- #
# 0) pandas_datareader: the cleanest pull of the CURRENT series
# --------------------------------------------------------------------- #
def fetch_current(
    series_id: str,
    start: str = "1948-01-01",
    end: str | None = None,
) -> pd.DataFrame:
    """Latest vintage of `series_id` via pandas_datareader -- the easy path.

    Returns a tidy [period, vintage_date, value] frame so it matches the other
    fetchers, but be honest about what it is: `vintage_date` is stamped as
    *today*, because pandas_datareader can only ever hand you the current
    revision. Do not mistake this for revision history -- use it as the
    "latest" leg and pair it with fetch_vintages_api/keyless for the past.
    """
    import pandas_datareader.data as web  # optional dependency

    s = web.DataReader(series_id, "fred", start, end)  # current vintage only
    s = s[series_id].dropna()
    return pd.DataFrame(
        {
            "period": pd.to_datetime(s.index),
            "vintage_date": pd.Timestamp.today().normalize(),
            "value": pd.to_numeric(s.values, errors="coerce"),
        }
    ).reset_index(drop=True)

FRED_API = "https://api.stlouisfed.org/fred/series/observations"
FREDGRAPH = "https://fred.stlouisfed.org/graph/fredgraph.csv"


# --------------------------------------------------------------------- #
# A) keyed API: full revision history in one call
# --------------------------------------------------------------------- #
def fetch_vintages_api(
    series_id: str,
    api_key: str,
    observation_start: str = "1948-01-01",
    realtime_start: str = "1900-01-01",
    realtime_end: str = "9999-12-31",
    timeout: int = 30,
) -> pd.DataFrame:
    """Return the complete bitemporal panel for `series_id` from FRED.

    Spanning realtime_start..realtime_end over all of history makes FRED return
    every revision. We map each revision to the date it first became known
    (realtime_start), giving tidy (period, vintage_date, value) rows.
    """
    params = {
        "series_id": series_id,
        "api_key": api_key,
        "file_type": "json",
        "observation_start": observation_start,
        "realtime_start": realtime_start,
        "realtime_end": realtime_end,
    }
    resp = requests.get(FRED_API, params=params, timeout=timeout)
    resp.raise_for_status()
    obs = resp.json()["observations"]

    df = pd.DataFrame(obs)
    df = df[df["value"] != "."]  # FRED's missing-value sentinel
    out = pd.DataFrame(
        {
            "period": pd.to_datetime(df["date"]),
            # realtime_start is the moment this value became the official answer
            "vintage_date": pd.to_datetime(df["realtime_start"]),
            "value": pd.to_numeric(df["value"], errors="coerce"),
        }
    ).dropna(subset=["value"])
    return (
        out.sort_values(["period", "vintage_date"])
        .drop_duplicates(["period", "vintage_date"], keep="last")
        .reset_index(drop=True)
    )


# --------------------------------------------------------------------- #
# B) keyless: one snapshot per requested vintage date
# --------------------------------------------------------------------- #
def fetch_snapshot_keyless(
    series_id: str,
    vintage_date: str,
    observation_start: str = "1948-01-01",
    observation_end: str = "2100-01-01",
    timeout: int = 30,
) -> pd.DataFrame:
    """Series `series_id` exactly as it stood on `vintage_date`, no key needed."""
    params = {
        "id": series_id,
        "cosd": observation_start,
        "coed": observation_end,
        "vintage_date": vintage_date,
    }
    resp = requests.get(FREDGRAPH, params=params, timeout=timeout)
    resp.raise_for_status()
    raw = pd.read_csv(io.StringIO(resp.text))
    raw.columns = ["period", "value"]
    raw["value"] = pd.to_numeric(raw["value"], errors="coerce")
    raw = raw.dropna(subset=["value"])
    raw["period"] = pd.to_datetime(raw["period"])
    raw["vintage_date"] = pd.to_datetime(vintage_date)
    return raw[["period", "vintage_date", "value"]].reset_index(drop=True)


def fetch_vintages_keyless(
    series_id: str, vintage_dates: list[str]
) -> pd.DataFrame:
    """Stack several keyless snapshots into one bitemporal panel."""
    frames = [fetch_snapshot_keyless(series_id, vd) for vd in vintage_dates]
    return (
        pd.concat(frames, ignore_index=True)
        .sort_values(["period", "vintage_date"])
        .reset_index(drop=True)
    )


# --------------------------------------------------------------------- #
if __name__ == "__main__":
    # the easy one-liner first: current series via pandas_datareader
    try:
        cur = fetch_current("UNRATE")
        print(
            f"fetch_current -> latest UNRATE vintage: {len(cur):,} months, "
            f"last = {cur['period'].max():%Y-%m} @ {cur['value'].iloc[-1]}"
        )
    except Exception as e:  # offline, or pandas_datareader/pandas version clash
        print(f"(skipped fetch_current: {type(e).__name__}: {e})")

    key = os.environ.get("FRED_API_KEY")
    if key:
        print("Fetching the full UNRATE revision history from FRED ...")
        df = fetch_vintages_api("UNRATE", api_key=key)
        out = os.path.join(
            os.path.dirname(__file__), "..", "data", "unrate_vintages_full.csv"
        )
        df.to_csv(out, index=False)
        print(
            f"wrote {len(df):,} facts across "
            f"{df['vintage_date'].nunique()} vintages -> {os.path.relpath(out)}"
        )
    else:
        print("No FRED_API_KEY set. Demonstrating the keyless route instead.")
        print("Get a free key at https://fred.stlouisfed.org/docs/api/api_key.html")
        df = fetch_vintages_keyless(
            "UNRATE",
            ["2018-02-02", "2020-05-08", "2025-07-03"],
        )
        print(df.groupby("vintage_date")["period"].agg(["count", "max"]))
