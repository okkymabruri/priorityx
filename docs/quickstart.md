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
results, stats = px.fit_priority_matrix(
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
movement, meta = px.track_cumulative_movement(
    df,
    entity_col="service",
    timestamp_col="date",
    quarters=["2024-01-01", "2025-01-01"]
)

# detect transitions
transitions = px.extract_transitions(movement)

# visualize transitions
px.plot_transition_timeline(transitions, entity_name="Service", save_plot=True)

# analyze drivers for specific transition
if not transitions.empty:
    first_transition = transitions.iloc[0]
    analysis = px.extract_transition_drivers(
        movement_df=movement,
        df_raw=df,
        entity_name=first_transition["entity"],
        quarter_from=first_transition["from_quarter"],
        quarter_to=first_transition["transition_quarter"],
        entity_col="service",
        timestamp_col="date",
        top_n_subcategories=5,
        min_subcategory_delta=2
    )
    px.display_transition_drivers(analysis)

    # subcategory columns (e.g., severity/product/topic) are auto-detected
    # when not provided; pass subcategory_cols=[...] to override.
```

## Data Requirements

Your data needs:
- Entity identifier column (e.g., service, component, department)
- Timestamp column (Date or Datetime type)
- Optional: Count metric column (defaults to row count)

## Output

By default, outputs saved to:
- **`plot/`** - All PNG visualizations (priority matrix, transitions, trajectories)
- **`results/`** - All CSV data files (entity scores, transitions, movement tracking)

You can customize output directories using the `output_dir` parameter in visualization functions.

## Deterministic runs

Set `PRIORITYX_GLMM_SEED` (or call `set_glmm_random_seed()`) before running analyses to obtain repeatable GLMM estimates during debugging or CI checks:

```bash
PRIORITYX_GLMM_SEED=1234 python your_script.py
```
