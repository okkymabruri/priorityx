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

```python
import pandas as pd
import priorityx as px

# load your raw events; keep identifiers lexical, including leading zeros
df = pd.read_csv("your_data.csv", dtype={"service": str})
df["date"] = pd.to_datetime(df["date"])

# fit priority matrix
results = px.fit_priority_matrix(
    df,
    entity_col="service",      # your entity column
    timestamp_col="date",      # your date column
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
    timestamp_col="date",
    quarters=["2024-01-01", "2025-01-01"],
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
    movement,
    entity_name="service",
    highlight_top_n=4,
    highlight_by="trajectory_distance",
    recent_periods=6,
    plot_path="trajectories.png",
)

# analyze drivers for a specific transition
analysis = px.extract_transition_drivers(
    movement_df=movement,
    df_raw=df,
    entity_name="Service A",
    period_from="2024-Q2",
    period_to="2024-Q3",
    entity_col="service",
    timestamp_col="date",
    subcategory_cols=["category", "region"],
    numeric_cols={"amount": [0, 1e6, 5e6, 10e6]},  # breakdown by amount bins
)
px.display_transition_drivers(analysis, save_txt=True, txt_path="drivers.txt")
```

## Data Requirements

Your data needs:

- Entity identifier column (e.g., service, component, department)
- Timestamp column (Date or Datetime type)
- Optional: Count metric column (defaults to row count)

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
