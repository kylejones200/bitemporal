# Learning Velocity: How Fast Does Data Converge to Truth?

Not all revisions are slow.

Shell's 2004 restatement of proved reserves was catastrophic, but it was fast. The company announced a 20% write-down in January 2004. By April 2004 — ten months after the original YE2002 booking — the number had settled. 87% of the total revision arrived in the first restatement. The knowledge clock needed only seven months to cross the halfway mark.

Contrast that with BLS unemployment revisions, which arrive years after the original publication. Periods that were first published in 2016 or 2017 didn't receive their final revision until the 2025 vintage — a gap of seven to nine years.

The difference isn't just magnitude. It's velocity. The code in `learning_velocity.py` measures this: for any bitemporal series, how fast does the preliminary estimate converge to the value the world eventually settles on?

---

## The convergence curve

For a single period, the convergence curve tracks what fraction of the total revision has arrived at each vintage date, indexed by months since the first publication.

```python
from bitemporal import BitemporalSeries
from learning_velocity import convergence_curve

s = BitemporalSeries.from_csv("data/unrate_vintages.csv")
curve = convergence_curve(s, "2017-09-01")

# index: months since first publication
# values: fraction of total revision accumulated
# 0     → 0.000  (nothing has arrived at first release, by definition)
# 89    → 1.000  (full revision arrived at the 2025 vintage)
```

The convergence curve starts at zero by construction: at the moment of first publication, no revision has yet occurred. It ends at 1.0 when the final value is reached. Everything in between describes the path — fast or slow, stepwise or gradual.

For the Shell YE2002 proved reserves, the curve has four data points:

| Lag (months) | Fraction revised |
|-------------|-----------------|
| 0           | 0.000            |
| 7           | 0.872            |
| 9           | 0.928            |
| 10          | 1.000            |

87.2% of the total revision arrived at the first restatement event, seven months after the original booking. The subsequent two restatements filled in the remaining 12.8%. The convergence curve is steep and fast.

---

## Half-life

The half-life summarizes the convergence curve in a single number: how many months pass before 50% of the total revision has arrived?

For step-function convergence curves — which are the norm for sparse vintage panels — the half-life is an upper bound. We know the 50% threshold was crossed somewhere between the previous vintage and the current one, but we don't have the intermediate data to pinpoint exactly when.

```python
from learning_velocity import half_life

# Shell YE2002: 50% arrived within 7 months (first restatement was at 87%)
hl_shell = half_life(shell_ye2002, "2002-12-31")
# → 7.0 months

# UNRATE 2017-09: 50% not crossed until the 89-month vintage
hl_unrate = half_life(s, "2017-09-01")
# → 89.0 months (upper bound)
```

Shell: ≤ 7 months. UNRATE: ≤ 89 months. Both are upper bounds because we only have discrete observation points, not the continuous underlying revision process.

---

## Estate velocity

The `estate_velocity(series)` function computes half-lives for every revised period in a series. The distribution of half-lives across the estate is what I call the learning velocity of a domain.

For the UNRATE panel:

- **26 revised periods**, all with half-lives between 27 and 89 months
- **Mean half-life: 50.1 months**
- **Median half-life: 44.5 months**

The half-lives cluster in three groups:
- **27 months**: periods revised in the 2018→2020 vintage pair (2.25 years between vintages)
- **62 months**: periods revised in the 2020→2025 vintage pair (5 years)
- **89 months**: a small cluster at the widest gap

These aren't true half-lives — they're the lag of the vintage that happened to carry the revision. With only five vintage dates, every revised period's "convergence" collapses into a single jump from 0% to 100%. We see when the revision landed; we don't see the continuous learning process that produced it.

For Shell reserves, the picture is richer:

- **2 revised periods** (YE2002 and YE2003)
- **Mean half-life: 7.5 months**
- **All periods converged within 12 months (100%)**

---

## Cross-domain comparison

The `compare_domains(*series_list, labels)` function puts both datasets side by side:

```
domain           n_revised  mean_half_life  pct_converged_12mo
UNRATE                  26            50.1                 0.0
Shell Reserves           2             7.5                 1.0
```

No UNRATE period converged within 12 months. Both Shell periods converged within 12 months.

This reflects a fundamental difference in revision mechanisms. BLS unemployment revisions accumulate gradually through seasonal re-estimation, population control updates, and benchmark revisions — processes that unfold over years. Shell's reserves revision was driven by a single investigation, producing a sharp, fast correction.

The learning velocity is a property of the revision *mechanism*, not the domain.

---

## What the convergence curve tells you about model risk

A slow-converging series is more dangerous to backtest than a fast-converging one. If the preliminary estimate is wrong for five years before the final value is known, any model trained on that five-year window was trained on wrong data. The model didn't know that at the time — it knew only what the data said as of the training date.

This is why the `as_of(period, knowledge_date)` semantics in `BitemporalSeries` matter. If your model consumes the series through the bitemporal engine, it will always see the value that was known on its training date — not the revised value that would have been known later. The convergence curve tells you how much the model's training data would have differed if you had waited longer.

A half-life of 50 months means that for the average period in this series, a model trained 50 months after publication was using a preliminary value that still had 50% of its eventual revision outstanding. A model trained the next day was using a value that had seen essentially no revision yet.

The operational implication: **the further back you train, the more your training data looks like the final values. The closer to the present you train, the more your training data reflects preliminary estimates.** This asymmetry doesn't disappear because you build your features from a point-in-time join — it just becomes explicit and manageable instead of latent and damaging.

---

## Figure 10

Figure 10 shows both domains side by side. The left panel is Shell's YE2002 convergence curve: a step function that reaches 87% at month 7, then grinds up to 100% by month 10. The right panel is a horizontal bar chart of UNRATE half-life upper bounds: every period in the panel has a half-life between 27 and 89 months, and none have converged within the 12-month dashed reference line.

The contrast is the story. One domain resolves quickly because the revision is driven by an external event. The other resolves slowly because the revision is driven by an ongoing process of data accretion.

---

## Code

```python
from bitemporal import BitemporalSeries
from reserves import load_shell_reserves
from learning_velocity import estate_velocity, compare_domains

unrate = BitemporalSeries.from_csv("data/unrate_vintages.csv")
shell  = load_shell_reserves()

ev = estate_velocity(unrate)
print(ev[["period", "half_life_months"]].to_string(index=False))

result = compare_domains(unrate, shell, labels=["UNRATE", "Shell Reserves"])
print(result)
```

Source: [`learning_velocity.py`](../learning_velocity.py) | [`tests/test_learning_velocity.py`](../tests/test_learning_velocity.py)
