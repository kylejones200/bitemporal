"""Tests for learning_velocity.py."""
import os
import sys
import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from bitemporal import BitemporalSeries
from reserves import load_shell_reserves
from learning_velocity import (
    convergence_curve,
    half_life,
    estate_velocity,
    compare_domains,
)

HERE = os.path.dirname(__file__)
CSV  = os.path.join(HERE, "..", "data", "unrate_vintages.csv")

s     = BitemporalSeries.from_csv(CSV)
shell = load_shell_reserves()


def test_convergence_curve_starts_at_zero():
    curve = convergence_curve(s, "2017-09-01")
    assert not curve.empty
    assert curve.iloc[0] == 0.0


def test_convergence_curve_ends_at_one():
    curve = convergence_curve(s, "2017-09-01")
    assert abs(curve.iloc[-1] - 1.0) < 1e-6


def test_convergence_curve_first_lag_is_zero():
    curve = convergence_curve(s, "2017-09-01")
    assert curve.index[0] == 0


def test_convergence_curve_empty_for_unrevised_period():
    # 2021-01-01 is present in the panel but never revised.
    # Pick a period that only exists in one vintage value.
    snap = s.snapshot("2018-02-02")
    all_periods = snap.index.tolist()
    rev = s.revised_periods()["period"].tolist()
    unrevised = [p for p in all_periods if p not in rev]
    if unrevised:
        curve = convergence_curve(s, str(unrevised[0].date()))
        assert curve.empty


def test_convergence_curve_shell_has_four_points():
    shell_ye2002 = BitemporalSeries(
        shell.frame[shell.frame["period"] == pd.Timestamp("2002-12-31")].copy()
    )
    curve = convergence_curve(shell_ye2002, "2002-12-31")
    assert len(curve) == 4


def test_convergence_curve_shell_reaches_one():
    shell_ye2002 = BitemporalSeries(
        shell.frame[shell.frame["period"] == pd.Timestamp("2002-12-31")].copy()
    )
    curve = convergence_curve(shell_ye2002, "2002-12-31")
    assert abs(curve.iloc[-1] - 1.0) < 1e-6


def test_half_life_positive_for_revised_period():
    hl = half_life(s, "2017-09-01")
    assert hl is not None
    assert hl > 0


def test_half_life_none_for_unrevised_period():
    snap = s.snapshot("2018-02-02")
    all_periods = snap.index.tolist()
    rev = s.revised_periods()["period"].tolist()
    unrevised = [p for p in all_periods if p not in rev]
    if unrevised:
        hl = half_life(s, str(unrevised[0].date()))
        assert hl is None


def test_shell_half_life_under_twelve_months():
    shell_ye2002 = BitemporalSeries(
        shell.frame[shell.frame["period"] == pd.Timestamp("2002-12-31")].copy()
    )
    hl = half_life(shell_ye2002, "2002-12-31")
    assert hl is not None
    assert hl <= 12


def test_estate_velocity_covers_all_revised_periods():
    ev = estate_velocity(s)
    rev = s.revised_periods()
    assert len(ev) == len(rev)


def test_estate_velocity_columns():
    ev = estate_velocity(s)
    for col in ["period", "total_revision", "n_revisions", "half_life_months"]:
        assert col in ev.columns


def test_compare_domains_includes_both_labels():
    result = compare_domains(s, shell, labels=["UNRATE", "Shell Reserves"])
    assert set(result["domain"]) == {"UNRATE", "Shell Reserves"}


def test_compare_domains_shell_faster_than_unrate():
    result = compare_domains(s, shell, labels=["UNRATE", "Shell Reserves"])
    hl_unrate = result.loc[result["domain"] == "UNRATE",    "mean_half_life"].iloc[0]
    hl_shell  = result.loc[result["domain"] == "Shell Reserves", "mean_half_life"].iloc[0]
    assert hl_shell < hl_unrate
