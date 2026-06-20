# Is Revision Random? The Statistical Structure of Data Uncertainty

The BLS releases the U.S. unemployment rate on the first Friday of every month. The number that lands on screens across trading desks, policy offices, and newsrooms is presented as a fact. But every economist who has worked with vintages of this data knows it isn't. It's a preliminary estimate — a best belief as of today, subject to revision.

The question nobody asks loudly enough is whether those revisions have structure.

If revisions are random, preliminary data is an unbiased estimator of the eventual final value. You can use it as-is, knowing that errors will wash out in expectation. But if revisions are structured — systematically positive, autocorrelated, or varying by lag — then every model trained on as-reported data carries a latent bias that compounds quietly over time.

The code in `revision_stats.py` runs three tests against the revision record: a normality test on the distribution, a directional bias test, and a Ljung-Box autocorrelation test.

---

## What the revision distribution looks like

The function `revision_distribution(series)` collects every signed delta across all vintage pairs and fits a Gaussian to the result. On the five-vintage UNRATE panel:

- **n = 26 revision events**
- **mean = +0.0154 pp** — a slight upward tilt
- **std = 0.0988 pp**
- **Gaussian fit:** μ = +0.0154, σ = 0.0988
- **Normality test:** stat = 68.19, **p < 0.0001**

The normality test rejects the Gaussian model emphatically. That isn't surprising once you look at the data: every single revision in this panel is either +0.1 or −0.1. No revision is larger; no revision is smaller. The distribution isn't bell-shaped — it's a two-point mass.

This is the BLS reporting precision boundary. The unemployment rate is published to one decimal place. A revision can only occur when the true rate crosses a 0.1pp threshold. The Gaussian overlay in fig8 is a mathematical fit to a distribution that is fundamentally discrete; it shows what we'd expect if this were a continuous process, and the data refuses to cooperate.

The scientific finding: **the revision distribution for BLS unemployment is not governed by statistical noise. It is governed by measurement precision.** This is actually a good result. It means the preliminary number is always within 0.1pp of the final value. But it also means that conventional confidence intervals (which assume continuous error distributions) need to be interpreted carefully.

---

## Is the direction biased?

The function `directional_bias(series)` runs a two-sided binomial test. The null hypothesis is that positive and negative revisions are equally likely — the sign of a revision is a coin flip.

On our panel:

- 15 revisions were upward
- 11 revisions were downward
- **Binomial p-value = 0.557**

With p = 0.557, we cannot reject the null. The upward tilt in the mean (+0.0154 pp) is not statistically distinguishable from chance with 26 observations. The BLS, at least across this five-vintage window, does not appear to systematically underestimate or overestimate unemployment.

This is the correct result for a well-designed statistical agency. Systematic directional bias would indicate either a methodological flaw or political pressure on preliminary estimates. Neither is apparent here.

The caveat: detecting a bias of 0.015 pp with 26 observations requires enormous statistical power. You would need several hundred revision events before a subtle directional tendency could be distinguished from sampling noise. The ALFRED database, which archives hundreds of BLS vintages going back to 1996, would provide the statistical power to run this test properly.

---

## Is there autocorrelation in revisions?

If revisions are serially correlated — if an upward revision to one month makes an upward revision to the next month more likely — then a model trained on revisions can predict the direction of future revisions. That's a much stronger signal than directional bias alone.

The function `revision_autocorrelation(series, max_lag)` runs the Ljung-Box portmanteau test on the sequence of signed revision deltas, ordered by the period they belong to.

On our panel (lags 1–6, max usable given n=26):

| Lag | Ljung-Box stat | p-value |
|-----|---------------|---------|
| 1   | 0.020         | 0.887   |
| 2   | 1.921         | 0.383   |
| 3   | 2.015         | 0.569   |
| 4   | 2.392         | 0.664   |
| 5   | 2.554         | 0.768   |

No lag is significant. There is no detectable autocorrelation structure in the revision sequence. Revisions appear to be approximately independent.

---

## How to use this in production

The `confidence_band(series, knowledge_date, level)` function packages these findings into an operational tool. For any snapshot date, it returns the current published values with an empirical confidence interval derived from the historical revision distribution:

```python
from revision_stats import confidence_band

band = confidence_band(s, "2018-02-02", level=0.95)
# period, point_estimate, lower, upper
# 2017-09-01   4.2   4.1   4.3
# ...
```

The interval is ±0.1 pp for this dataset — because that is the only revision magnitude we have ever observed. In a richer dataset (with continuous revision distributions), the interval would be tighter or wider depending on the historical volatility of that series.

This is the honest version of "error bars on preliminary data." It doesn't require distributional assumptions. It asks only: given what this series has historically done, how wrong could the current published value be?

---

## The right dataset for this question

Five vintages is not enough. The findings reported here — no bias, no autocorrelation, discrete ±0.1 distribution — are consistent with a well-behaved BLS series, but they are also consistent with a dataset too small to detect any of these effects.

The proper analysis requires the full ALFRED panel (200+ vintages, covering 1996 to present). With that data:

1. The revision distribution becomes continuous — revisions of 0.05pp, 0.15pp, and larger are common over longer horizons.
2. The directional bias test gains power sufficient to detect a 0.02pp systematic tendency.
3. The Ljung-Box test can distinguish true independence from low-frequency autocorrelation.

The `revision_stats.py` functions are ready for that richer dataset. The five-vintage panel shows the structure of the analysis; the ALFRED panel would populate it with statistically meaningful results.

---

## Code

```python
from bitemporal import BitemporalSeries
from revision_stats import revision_distribution, directional_bias, revision_autocorrelation

s    = BitemporalSeries.from_csv("data/unrate_vintages.csv")
dist = revision_distribution(s)
bias = directional_bias(s)
acf  = revision_autocorrelation(s)

print(f"Mean revision: {dist['mean']:+.4f} pp")
print(f"Bias p-value:  {bias['p_value']:.4f}")
print(acf)
```

Source: [`revision_stats.py`](../revision_stats.py) | [`tests/test_revision_stats.py`](../tests/test_revision_stats.py)
