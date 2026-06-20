"""
test_bitemporal.py -- run with:  python3 -m pytest src/test_bitemporal.py -q
                       or simply: python3 src/test_bitemporal.py
"""

from __future__ import annotations

import os

import pandas as pd

from bitemporal import BitemporalSeries

HERE = os.path.dirname(os.path.abspath(__file__))
CSV = os.path.join(HERE, "..", "data", "unrate_vintages.csv")


def _toy() -> BitemporalSeries:
    # period 2017-09 reported 4.2 then revised to 4.3; 2020-04 went 14.7 -> 14.8
    df = pd.DataFrame(
        {
            "period": ["2017-09-01", "2017-09-01", "2020-04-01", "2020-04-01"],
            "vintage_date": ["2018-02-02", "2025-07-03", "2020-05-08", "2025-07-03"],
            "unrate": [4.2, 4.3, 14.7, 14.8],
        }
    )
    df.to_csv("/tmp/_toy.csv", index=False)
    return BitemporalSeries.from_csv("/tmp/_toy.csv")


def test_as_of_respects_transaction_time():
    s = _toy()
    # Before the value was ever published, we honestly know nothing.
    assert s.as_of("2020-04-01", "2019-01-01") is None
    # On a date after the first print but before the revision, we see the first print.
    assert s.as_of("2020-04-01", "2020-06-01") == 14.7
    # After the revision, we see the revised value.
    assert s.as_of("2020-04-01", "2030-01-01") == 14.8


def test_snapshot_is_point_in_time():
    s = _toy()
    snap_2019 = s.snapshot("2019-01-01")
    # Only 2017-09 was knowable in early 2019 (2020-04 hadn't happened).
    assert list(snap_2019.index.strftime("%Y-%m")) == ["2017-09"]
    assert snap_2019.iloc[0] == 4.2


def test_revision_history_collapses_unchanged():
    s = _toy()
    hist = s.revision_history("2017-09-01")
    assert hist["value"].tolist() == [4.2, 4.3]
    assert s.first_release("2017-09-01") == 4.2
    assert s.latest("2017-09-01") == 4.3
    assert s.total_revision("2017-09-01") == 0.1


def test_scd2_intervals_are_contiguous_and_closed():
    s = _toy()
    scd2 = s.to_scd2()
    apr = scd2[scd2["period"] == pd.Timestamp("2020-04-01")].sort_values("know_from")
    assert apr["value"].tolist() == [14.7, 14.8]
    # the first interval closes exactly where the next opens
    assert apr.iloc[0]["know_to"] == apr.iloc[1]["know_from"]
    # the last interval is open (still current)
    assert pd.isna(apr.iloc[1]["know_to"])
    assert apr.iloc[1]["is_current"]


def test_real_panel_loads_and_april_2020_revised():
    s = BitemporalSeries.from_csv(CSV)
    assert s.as_of("2020-04-01", "2020-06-01") == 14.7
    assert s.as_of("2020-04-01", "2025-12-01") == 14.8
    # the documented 1990 example survived the build
    assert s.first_release("1990-01-01") == 5.3
    assert s.latest("1990-01-01") == 5.4


def _run_all():
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"  PASS  {fn.__name__}")
    print(f"\n{len(fns)} tests passed.")


if __name__ == "__main__":
    _run_all()
