# Quick Start

## Installation

```bash
pip install priorityx
```

## Basic Usage

```python
import polars as pl
from priorityx.core.glmm import fit_priority_matrix
from priorityx.viz.matrix import plot_priority_matrix

# load your data
df = pl.read_csv("your_data.csv")

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
```

## Data Requirements

Your data needs:
- Entity identifier column (e.g., service, component, department)
- Timestamp column (Date or Datetime type)
- Optional: Count metric column (defaults to row count)

## Output

Results include:
- Priority matrix: CSV + scatter plot
- Transitions: CSV + timeline heatmap
- Movement: CSV + trajectory plot

Outputs saved to `plot/` and `results/` directories.
