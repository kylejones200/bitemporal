"""Tests for revision_stats.py."""
import os
import sys
import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from bitemporal import BitemporalSeries
from revision_stats import (
    revision_distribution,
    directional_bias,
    revision_autocorrelation,
    confidence_band,
)

HERE = os.path.dirname(__file__)
CSV  = os.path.join(HERE, "..", "data", "unrate_vintages.csv")

s = BitemporalSeries.from_csv(CSV)


def test_revision_distribution_returns_expected_count():
    dist = revision_distribution(s)
    assert dist["n"] == 26


def test_all_deltas_bounded_by_bls_precision():
    dist = revision_distribution(s)
    assert all(abs(d) <= 0.1 + 1e-9 for d in dist["deltas"])


def test_normality_rejected_for_bimodal_data():
    dist = revision_distribution(s)
    # The {-0.1, +0.1} distribution is bimodal and definitively non-normal.
    assert dist["normality_p"] < 0.05


def test_gaussian_fit_mu_near_zero():
    dist = revision_distribution(s)
    # With roughly equal positive and negative revisions the fit mean is near 0.
    assert abs(dist["norm_fit_mu"]) < 0.05


def test_directional_bias_not_significant():
    bias = directional_bias(s)
    # 15 positive / 11 negative out of 26 is not statistically significant.
    assert bias["p_value"] > 0.05


def test_directional_bias_counts_sum_to_total():
    bias = directional_bias(s)
    dist = revision_distribution(s)
    assert bias["n_positive"] + bias["n_negative"] + bias["n_zero"] == dist["n"]


def test_autocorrelation_returns_dataframe():
    acf = revision_autocorrelation(s)
    assert not acf.empty
    assert "lb_pvalue" in acf.columns


def test_autocorrelation_no_significant_lags():
    acf = revision_autocorrelation(s)
    # Ljung-Box should find no significant autocorrelation at any lag.
    assert (acf["lb_pvalue"] > 0.05).all()


def test_confidence_band_has_correct_columns():
    band = confidence_band(s, "2020-05-08")
    for col in ["period", "point_estimate", "lower", "upper", "q_low", "q_high"]:
        assert col in band.columns


def test_confidence_band_lower_le_upper():
    band = confidence_band(s, "2020-05-08")
    assert (band["lower"] <= band["upper"] + 1e-9).all()


def test_confidence_band_symmetric_for_zero_mean():
    band = confidence_band(s, "2020-05-08")
    # q_low and q_high should be symmetric (both ±0.1) for a zero-mean distribution.
    assert abs(band["q_low"].iloc[0] + band["q_high"].iloc[0]) < 1e-9


def test_empty_series_returns_empty():
    empty = BitemporalSeries(s.frame.iloc[:0].copy())
    assert revision_distribution(empty) == {}
    assert directional_bias(empty) == {}
    assert confidence_band(empty, "2020-05-08").empty
