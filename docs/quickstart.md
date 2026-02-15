# Quick Start

## Installation

```bash
pip install priorityx
```

## Basic Usage

```python
import pandas as pd
import priorityx as px

# load your data
df = pd.read_csv("your_data.csv")
df["date"] = pd.to_datetime(df["date"])

# fit priority matrix
results = px.fit_priority_matrix(
    df,
    entity_col="service",      # your entity column
    timestamp_col="date",      # your date column
    temporal_granularity="quarterly",
    min_observations=8,
)

# visualize
px.plot_priority_matrix(results, entity_name="Service", save_plot=True)
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
px.plot_transition_timeline(transitions, entity_name="Service", save_plot=True)

# plot trajectories (auto-select top 4 movers from last 6 quarters)
px.plot_entity_trajectories(
    movement,
    entity_name="service",
    highlight_top_n=4,
    highlight_by="trajectory_distance",
    recent_periods=6,
    save_plot=True,
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

By default, outputs saved to:

- **`results/plot/`** — PNG visualizations (priority matrix, transitions, trajectories)
- **`results/csv/`** — CSV tables (entity scores, transitions, movement tracking)

You can customize output directories using the `plot_dir` / `csv_dir` / `output_dir` parameters in visualization functions.

## Deterministic runs

Set `PRIORITYX_GLMM_SEED` (or call `set_glmm_random_seed()`) before running analyses to obtain repeatable GLMM estimates during debugging or CI checks:

```bash
PRIORITYX_GLMM_SEED=1234 python your_script.py
```
