# Methodology

## Scope

PriorityX estimates entity-level score positions with generalized linear mixed
models (GLMMs), classifies their signs into quadrants, and tracks changes across
cumulative fits. Scores and event classes are model outputs; they do not establish
causation, verified distress or a universal ordering of operational urgency.

## Models and aggregation

For the default count-based analysis, events are aggregated by entity and period.
Without `count_col`, the response is the number of rows. The single-model and
separate-model count paths sum `count_col` within each entity-period when
provided. Custom `x_metric` / `y_metric`
columns are averaged within each entity-period and fitted with Gaussian or Gamma
models. Gamma uses a log link and excludes non-positive aggregated metric values.

The fixed-effect formula is:

```text
response ~ time + seasonal_effects
```

There are separate entity random-intercept and random-slope variance-component
blocks. Seasonal dummies use quarter, semester or month, and are included only
when the prepared data span at least two calendar years. Time is centered and
measured in years, including fractional years for finer cadences.

Count models use `PoissonBayesMixedGLM.fit_vb()`. Continuous metrics use the
statsmodels Bayesian mixed-model interface with method fallbacks; inspect
`return_stats=True` for the method actually used. The default prior scales are
`vcp_p=3.5` for random-effect standard deviations and `fe_p=3.0` for fixed effects.
These settings are modeling choices, not evidence of a calibrated detection rate.

One model is fitted when both axis metrics are the same, including the default
where both are `None`. Different axis metrics use separate fits and retain the
intersection of their fitted entities. `x_effect` / `y_effect` select intercept
or slope; their defaults are intercept for X and slope for Y. Choosing a custom
Y metric alone therefore uses that metric's **slope** unless `y_effect` is changed.

## Reading scores and quadrants

| Score, default count model | Component | Interpretation |
|---|---|---|
| `x_score` | Entity random intercept | Deviation from the common fitted log-count level |
| `y_score` | Entity random slope | Deviation from the common fitted time trend, per year |

For a count-model intercept deviation of 0.5, `exp(0.5)` is about 1.65: a
multiplicative effect relative to the common fitted level, conditional on the
other model terms. It is not a direct comparison with the raw observed average.
Continuous-metric intercepts and slopes are each z-standardized across fitted
entities before axis selection. Their score scale differs from count models.

Quadrants depend **only on the signs of the selected scores**:

| Quadrant | X | Y |
|---|---|---|
| Q1 | `> 0` | `> 0` |
| Q2 | `<= 0` | `> 0` |
| Q3 | `<= 0` | `<= 0` |
| Q4 | `> 0` | `<= 0` |

There is no minimum-count rule inside quadrant classification. Count and
observation filters determine which entities are fitted; plot-label filters
control display. The [event-class rules](priority_classification.md) are a
separate layer and must not be inferred from quadrant colors alone.

## Inclusion and missing periods

- `min_total_count` filters on input **row counts per entity**, including when
  `count_col` supplies a different aggregated response. The returned `count`
  also records event rows rather than the sum of `count_col`.
- `min_observations` counts observed entity-period rows. Its argument default is
  3; a value of 3 is adjusted to 8 for Quarterly and 4 for Semiannual. Yearly and
  Monthly retain 3. Other explicit values are used directly.
- Direct `fit_priority_matrix()` staleness filtering applies only to Quarterly,
  using approximately `decline_window_quarters * 91` days before the latest
  retained data date. A non-positive value disables it.
- Missing entity-period combinations are not automatically filled with zeros.
  Count models drop non-positive aggregated counts; metric models drop missing
  aggregated values. Fit availability is not a measure of data completeness.

The fitting API defaults to **Yearly**, while movement tracking defaults to
**Quarterly** and AutoViz opens Quarterly when available. Set cadence explicitly
in analysis calls when comparing outputs.

## Cumulative movement

`track_movement()` supports Quarterly and Monthly schedules:

1. Fit a global reference on the full supplied dataset.
2. Select the endpoint population using row counts and an approximately
   91-days-per-quarter inactivity window, including for Monthly schedules.
3. Refit cumulative data strictly before each scheduled cutoff for that population.
   These fits disable per-fit observation, count and staleness filters. Periods
   with fewer than 100 cumulative rows or a fitting exception are skipped.
4. Calculate X/Y deltas and `period_count` between successive available fitted
   rows. The first delta is missing; a gap can make a delta span multiple periods.

A date-range schedule uses an **exclusive** end boundary. The global reference
uses the full input even if the schedule ends earlier; filter the input first
when an analysis must exclude later observations. Existing metadata names such
as `quarter_schedule` are retained for Monthly too.

## Events, display and validation

`extract_transitions()` selects events from movement history. Its saved
`risk_level`, within-quadrant extraction thresholds and rendering-time event
classes are distinct; [priority classification](priority_classification.md)
describes their precedence and limits. Driver breakdowns compare
[calendar-quarter raw-event windows](api-reference.md#driver-period-windows)
and describe event-count changes rather than causes of model-score changes.

AutoViz and its opt-in static renderer read saved results and share display
semantics. Changing layout, selection or a YTD window does not run these models.
The original Matplotlib plotting functions retain their own display defaults.

Repository tests cover API and rendering contracts. They do not establish a
published accuracy, lead-time advantage or false-positive rate. Validate model
fit, missingness, cohort choices, score scales and operational thresholds on your
own historical data before relying on alerts.

Set `PRIORITYX_GLMM_SEED` before starting Python, or call
`set_glmm_random_seed()` before fitting, for repeatability within a fixed software
and data environment. A seed does not guarantee identical estimates across
statsmodels, numerical-library or platform changes.
