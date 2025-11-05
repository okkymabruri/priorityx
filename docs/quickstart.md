# Quick Start

## Installation

```bash
pip install priorityx
```

## Basic Usage

```python
import pandas as pd
from priorityx.core.glmm import fit_priority_matrix
from priorityx.viz.matrix import plot_priority_matrix

# load your data
df = pd.read_csv("your_data.csv")
df["date"] = pd.to_datetime(df["date"])

# fit priority matrix
results, stats = fit_priority_matrix(
    df,
    entity_col="service",      # your entity column
    timestamp_col="date",      # your date column
    temporal_granularity="quarterly",
    min_observations=8
)

# visualize
plot_priority_matrix(results, entity_name="Service", save_plot=True)
```

## Full Workflow

```python
from priorityx.tracking.movement import track_cumulative_movement
from priorityx.tracking.transitions import extract_transitions
from priorityx.tracking.drivers import extract_transition_drivers, display_transition_drivers
from priorityx.viz.timeline import plot_transition_timeline

# track movement over time
movement, meta = track_cumulative_movement(
    df,
    entity_col="service",
    timestamp_col="date",
    quarters=["2024-01-01", "2025-01-01"]
)

# detect transitions
transitions = extract_transitions(movement)

# visualize transitions
plot_transition_timeline(transitions, entity_name="Service", save_plot=True)

# analyze drivers for specific transition
if not transitions.empty:
    first_transition = transitions.iloc[0]
    analysis = extract_transition_drivers(
        movement_df=movement,
        df_raw=df,
        entity_name=first_transition["entity"],
        quarter_from=first_transition["from_quarter"],
        quarter_to=first_transition["transition_quarter"],
        entity_col="service",
        timestamp_col="date"
    )
    display_transition_drivers(analysis)
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
