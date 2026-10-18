# Quick Start

## Installation

Follow [installation](installation.md) for Python requirements and environment
setup on macOS, Linux and Windows.

## Open existing results in AutoViz

Run `python -m priorityx app`, then open a result bundle or import saved CSVs.
To load a bundle immediately, run `python -m priorityx app --bundle results.json`.
Try the [saved IT incidents sample](autoviz-example.md) for a complete example.
The [workspace guide](app.md) covers linked charts, layout and exports; the
[saved-result contract](saved-results.md#required-columns) lists required
identity and period columns. This route does not fit models.

## Basic Usage

This analysis example uses the repository's generated IT incidents CSV (download
requires a connection). It covers 2023–2025 and fits models when you run it.
For your own data, replace the URL and pass your actual identifier/date columns.

```python
import pandas as pd
import priorityx as px

# keep identifiers lexical, including leading zeros
url = (
    "https://raw.githubusercontent.com/okkymabruri/priorityx/main/"
    "examples/incidents/incidents.csv"
)
df = pd.read_csv(url, dtype={"service": str}, parse_dates=["opened_at"])

# fit priority matrix
results = px.fit_priority_matrix(
    df,
    entity_col="service",      # your entity column
    timestamp_col="opened_at", # your date column
    temporal_granularity="quarterly",
    min_observations=8,
)

# visualize and save explicitly
px.plot_priority_matrix(results, entity_name="Service", plot_path="matrix.png")
```

## Full Workflow

```python
import priorityx as px

# track movement over time
movement = px.track_movement(
    df,
    entity_col="service",
    timestamp_col="opened_at",
    quarters=["2023-01-01", "2026-01-01"],
    temporal_granularity="quarterly",
)

# detect transitions
transitions = px.extract_transitions(movement)

# visualize transitions
px.plot_transition_timeline(
    transitions, movement_df=movement, entity_name="Service",
    plot_path="transitions.png",
)

# plot trajectories (auto-select top 4 movers from last 6 quarters)
px.plot_entity_trajectories(
    movement.drop(columns=["last_active_quarter"], errors="ignore"),
    entity_name="service",
    highlight_top_n=4,
    highlight_by="trajectory_distance",
    recent_periods=6,
    plot_path="trajectories.png",
)
```

Driver breakdowns are described in the [API reference](api-reference.md#extract_transition_drivers).
They use matching calendar-quarter raw-event windows and do not fit a new model.

## Save results for AutoViz

Keep the complete analytical tables, before selecting chart subsets:

```python
from priorityx.results import ResultBundle, import_results_csv

# Event-free extraction can return no headers; retain a valid empty schema.
if transitions.empty:
    transitions = transitions.reindex(columns=[
        "entity", "transition_quarter", "from_quadrant", "to_quadrant", "risk_level"
    ])

dataset = import_results_csv(
    entity_type="service", type_label="Services", cadence="quarterly",
    source_id="it-incidents-example", coverage_start="2023-Q1", as_of="2025-Q4",
    matrix=results, movement=movement, transitions=transitions,
)
ResultBundle([dataset]).save("results.json")
```

These dates match the explicit tracking range above; use your actual coverage
and snapshot date. The matrix and movement calls must use the intended input
coverage: a schedule alone does not filter the global baseline or matrix fit.
Then open `python -m priorityx app --bundle results.json`.

## Data Requirements

Your data needs:

- Entity identifier column (e.g., service, component, department); use consistent
  string identifiers across tables for AutoViz
- Timestamp column (Date or Datetime type)
- Optional count-response column (summed per entity-period) or continuous metric
  columns (averaged per entity-period)

The default fitting cadence is Yearly. The examples above set Quarterly explicitly;
its default effective observation minimum is eight observed periods. A short
tracking range can still use a longer cumulative input history. Review
[methodology](methodology.md) before changing thresholds to make a fit run.

## Output

Analysis functions return tables; saving is explicit. Save complete result
tables using `results.to_csv("priority_matrix.csv", index=False)`,
`movement.to_csv("movement.csv", index=False)` and
`transitions.to_csv("transitions.csv", index=False)`, then create a
[bundle for AutoViz](saved-results.md#build-and-open-a-bundle).
For plot helpers, `plot_path` / `csv_path` specify exact output paths and imply
saving. Older directory/save flags remain compatibility options; see
[output naming](output_naming.md).

## Deterministic runs

Set `PRIORITYX_GLMM_SEED` (or call `set_glmm_random_seed()`) before running analyses to obtain repeatable GLMM estimates during debugging or CI checks:

```bash
PRIORITYX_GLMM_SEED=1234 python your_script.py
```
