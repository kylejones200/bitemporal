"""Tests for vintage_ensemble.py."""
import os
import sys
import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from bitemporal import BitemporalSeries
from vintage_ensemble import VintageEnsemble

HERE = os.path.dirname(__file__)
CSV  = os.path.join(HERE, "..", "data", "unrate_vintages.csv")

s  = BitemporalSeries.from_csv(CSV)
ve = VintageEnsemble(s)


def test_uncertainty_band_returns_tuple():
    band = ve.uncertainty_band("2017-09-01")
    assert band is not None
    assert len(band) == 2


def test_uncertainty_band_lower_le_upper():
    band = ve.uncertainty_band("2017-09-01")
    assert band[0] <= band[1] + 1e-9


def test_uncertainty_band_width_equals_ci_width():
    band = ve.uncertainty_band("2017-09-01")
    # The empirical CI spans -0.1 to +0.1 → width of 0.2 pp.
    width = band[1] - band[0]
    assert abs(width - 0.2) < 1e-9


def test_uncertainty_band_none_for_unknown_period():
    band = ve.uncertainty_band("1800-01-01")
    assert band is None


def test_coverage_rate_returns_complete_dict():
    cr = ve.coverage_rate()
    for key in ["n_tested", "n_covered", "coverage", "level_requested"]:
        assert key in cr


def test_coverage_rate_n_tested_equals_revised_count():
    cr = ve.coverage_rate()
    rev = s.revised_periods()
    assert cr["n_tested"] == len(rev)


def test_in_sample_coverage_is_perfect():
    # CI derived from the same 26 observations should cover all 26 in-sample.
    cr = ve.coverage_rate(level=0.95)
    assert cr["coverage"] == 1.0


def test_ensemble_snapshot_has_ordered_bands():
    snap = ve.ensemble_snapshot("2020-05-08")
    assert "lower" in snap.columns
    assert "upper" in snap.columns
    assert "point_estimate" in snap.columns
    assert (snap["lower"] <= snap["point_estimate"] + 1e-9).all()
    assert (snap["point_estimate"] <= snap["upper"] + 1e-9).all()


def test_ensemble_snapshot_point_matches_series_snapshot():
    snap_ve = ve.ensemble_snapshot("2020-05-08")
    snap_s  = s.snapshot("2020-05-08")
    assert abs(snap_ve["point_estimate"].values - snap_s.values).max() < 1e-9
