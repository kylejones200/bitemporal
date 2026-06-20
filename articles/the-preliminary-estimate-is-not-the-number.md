# The Preliminary Estimate Is Not the Number

When the BLS releases the unemployment rate, the number on the press release is a point estimate. It occupies one cell on a spreadsheet. It feeds one row in a model. It shows up on one line of a policy memo.

It is not the number. It is the center of a distribution. The distribution has a range — bounded by measurement precision on one end and the economic complexity of the thing being measured on the other. The preliminary estimate is your best guess at the center, and the bounds describe how far wrong that guess could realistically be.

The code in `vintage_ensemble.py` operationalizes this idea. It takes the historical revision record of a series and uses it to build an empirical confidence interval around any preliminary value.

---

## The ensemble idea

A vintage ensemble treats every vintage of a series as a draw from the distribution of possible beliefs about history. If the final published value for a given month is the "true" answer, and we have ten intermediate vintages, we have ten different distances between "what we knew then" and "what we now believe to be true."

The distribution of those distances — across all periods in the panel — is the revision distribution. And an empirical confidence interval is just the quantiles of that distribution applied to any new preliminary value:

```
lower = preliminary + q₀.₀₂₅ (of all historical revision deltas)
upper = preliminary + q₀.₉₇₅ (of all historical revision deltas)
```

This requires no distributional assumptions. It asks only: what has this series historically done?

---

## The coverage backtest

A confidence interval isn't useful unless it is calibrated. A 95% interval should contain the eventual final value 95% of the time. More is over-conservative (too wide to be useful); less is under-conservative (false confidence).

The function `VintageEnsemble.coverage_rate(level)` runs this backtest:

```python
from bitemporal import BitemporalSeries
from vintage_ensemble import VintageEnsemble

s  = BitemporalSeries.from_csv("data/unrate_vintages.csv")
ve = VintageEnsemble(s)

cr = ve.coverage_rate(level=0.95)
# n_tested:  26
# n_covered: 26
# coverage:  1.000
# CI width:  [-0.10, +0.10] pp
```

The in-sample coverage is 100%.

This deserves an honest explanation. When you derive a confidence interval from the same 26 observations you use to evaluate it, you should expect near-perfect in-sample fit. That's not a coincidence; it's what "empirical" means. The CI uses ±0.1 pp because ±0.1 is the only revision magnitude we have ever observed in this panel — and so every revised period's final value naturally falls within ±0.1 of its first release.

The meaningful calibration test requires out-of-sample evaluation: train the CI on the first 80% of vintages, evaluate on the remaining 20%. That test requires the full ALFRED panel (200+ vintages). On five vintages, we can demonstrate the machinery; we cannot stress-test the calibration.

---

## What the fan chart shows

Figure 9 shows the five-year window from 2013 to 2018, visible from three knowledge dates — the 2018 first release, the 2020 revision, and the 2025 final. The gray band is the empirical 95% interval: ±0.1 pp around the 2018 preliminary estimate.

All subsequent vintages fell inside that band. This is both the expected result and the point: an analyst working in early 2018 could have said, with confidence grounded in the prior revision record, "this number will not change by more than 0.1 pp." That is a meaningful operational constraint. It tells you:

- A recession call based on the unemployment rate is not going to be reversed by a later revision.
- A model trained on preliminary data will not be systematically wrong by more than 0.1 pp.
- A policy memo citing the preliminary rate is not going to be contradicted by a later revision.

The band is narrow enough to be useful and honest enough to be real.

---

## The ensemble snapshot

The function `VintageEnsemble.ensemble_snapshot(knowledge_date)` extends the idea to the full series. Instead of a point-in-time snapshot (as returned by `BitemporalSeries.snapshot()`), it returns a DataFrame with three columns per period:

```
period      point_estimate  lower  upper
2017-09-01  4.2             4.1    4.3
2017-10-01  4.2             4.1    4.3
2017-11-01  4.1             4.0    4.2
...
```

This is what a publication-quality table should look like. Every row reports not just what the system believes, but how confident it is. Any consumer of this data — a trading model, a policy document, a risk report — can decide for itself how to handle the uncertainty.

The ensemble snapshot is also what a temporal feature store should produce. The two-clock model gives you point-in-time correctness; the ensemble adds the epistemic layer. Together they answer both questions: "what did we know on this date?" and "how certain were we?"

---

## When three dimensions aren't enough

This analysis works well for a series like BLS unemployment because the revision distribution is tightly bounded. The situation is more complex for series where:

1. **Revisions are unbounded.** Corporate earnings restatements, oil reserve write-downs, and census population estimates can revise by 5%, 30%, or 100%. The empirical CI for those series would be wide — correctly.

2. **The revision distribution is non-stationary.** A series that revised by ±0.1 pp from 1990 to 2010 and by ±0.5 pp from 2010 to 2020 should use a rolling window for the CI, not the full history.

3. **The vintage depth varies by period.** A newly published period has been observed once; a period published ten years ago has been observed hundreds of times. The uncertainty should be higher for the former. `VintageEnsemble` treats all periods equally; a production system should weight by vintage depth.

These limitations are documented not to dismiss the approach but to mark the frontier of the problem. The machinery in `vintage_ensemble.py` handles the common case correctly and provides a foundation for the extensions.

---

## Code

```python
from bitemporal import BitemporalSeries
from vintage_ensemble import VintageEnsemble

s  = BitemporalSeries.from_csv("data/unrate_vintages.csv")
ve = VintageEnsemble(s)

# Snapshot with uncertainty bands
snap = ve.ensemble_snapshot("2018-02-02")
print(snap.tail())

# Calibration backtest
cr = ve.coverage_rate(level=0.95)
print(f"Coverage: {cr['coverage']:.1%} ({cr['n_covered']}/{cr['n_tested']})")
```

Source: [`vintage_ensemble.py`](../vintage_ensemble.py) | [`tests/test_vintage_ensemble.py`](../tests/test_vintage_ensemble.py)
