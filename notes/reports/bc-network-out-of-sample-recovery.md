# Out-of-sample recovery

## Question

Does rolling recovery from first-year scope deferral hold when future cost, productivity, and capacity
factors are resampled rather than reused from the original episode?

## Method

- 20 rolling episodes, first-year risk-ranked deferral.
- 20% target, 21.3% actual mean deferred fraction.
- Five independent future-factor paths per episode, 100 paths total.
- 2028-2031 re-solved with the rolling persistence forecast and a two-year lookahead.
- Future factors sampled independently from the same lognormal assumptions.

## Results

| Metric | P10 | P50 | P90 | Mean |
|---|---:|---:|---:|---:|
| Final risk gap | -0.0078 | -0.0010 | 0.0072 | -0.0008 |
| Recovery | 0.0340 | 0.0421 | 0.0491 | 0.0421 |
| Reoptimized cost | 284,835 | 285,927 | 286,788 | 285,868 |
| No-reoptimization cost | 227,290 | 249,930 | 272,072 | 251,312 |
| Full policy cost | 273,213 | 295,899 | 326,472 | 299,052 |

- Final gap within 0.005: **87.0% of paths**.
- Median final gap is slightly negative, meaning the reoptimized path ends below the full policy's final risk.

The recovery result is not dependent on the original future-factor path. However, the reoptimized path
spends about 34,556 CAD more than no reoptimization on average, while remaining about 13,184 CAD below
the full policy.

## Interpretation

Out-of-sample future factors preserve the recovery conclusion: reoptimizing future years closes most
or all of the first-year deferral gap. The trade is additional future treatment cost relative to doing
nothing after deferral, but still lower total cost than the full policy on average.

This is not a stochastic multi-year policy guarantee. The first-year deferral is fixed, future factors
are independent, and the rolling policy is a persistence-forecast heuristic.

## Limits

- Five future paths per episode; 100 paths total.
- First-year deferral fixed; later plans cannot reverse it.
- Independent annual factors; no serial correlation or calibrated forecast model.
- No recurrence, weather, outage, safety, or asset-owner priority model.
