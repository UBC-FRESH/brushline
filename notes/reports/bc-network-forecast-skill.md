# Forecast-skill sensitivity

## Question

Does better calendar forecast information improve weather-aware recourse, or does the deferral
policy remain conservative even with perfect annual forecasts?

## Method

- 20 episodes, seed 7; same network and factors.
- Forecast skill is a coarse mixture: with probability equal to skill, the annual forecast equals
  the actual calendar; otherwise it is an independent synthetic draw.
- Skill 0 is independent; skill 1 is perfect.
- Forecast-aware execution plans against the forecast and executes under the actual calendar.
- Whole-action deferral when a forecast calendar cannot fit an action.

## Results

| Forecast skill | Completed scope P50 | Retained scope P50 | Mean risk | Cost P50 | Unscheduled h |
|---:|---:|---:|---:|---:|---:|
| 0% | 86.2% | 88.3% | 0.0526 | 264,470 | 64.7 |
| 50% | 88.0% | 88.8% | 0.0497 | 264,723 | 41.9 |
| 100% | 87.6% | 87.6% | 0.0502 | 264,047 | 0.0 |

Unscheduled work falls monotonically as forecast skill rises. Completion and risk are not
monotonic: mid-skill planning retains more scope and happens to complete more, while perfect
forecast is conservative because it defers whole actions until the observed calendar fits.

## Interpretation

Forecast skill primarily reduces unscheduled work; it does not guarantee better scope or risk. The
perfect-forecast case is an upper bound on calendar information but not an upper bound on
completion, because the aware policy drops whole actions rather than partially treating them. This
is a diagnostic, not a forecast product or stochastic dynamic program.

## Limits

- Perfect/independent mixture, not a calibrated forecast.
- One annual forecast realization; no within-year updates.
- Whole-action deferral; no partial treatment credit.
- No safety, access, field calibration, or asset-owner priority claim.
