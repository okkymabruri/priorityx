# API Reference

## Core Functions

### fit_priority_matrix

```python
from priorityx.core.glmm import fit_priority_matrix

results, stats = fit_priority_matrix(
    df,
    entity_col,
    timestamp_col,
    count_col=None,
    date_filter=None,
    min_observations=3,
    min_total_count=0,
    decline_window_quarters=6,
    temporal_granularity="yearly",
    vcp_p=3.5,
    fe_p=3.0
)
```

Fits Poisson GLMM to classify entities into priority quadrants.

**Parameters:**
- `df`: polars DataFrame
- `entity_col`: Entity identifier column name
- `timestamp_col`: Date column name
- `count_col`: Count metric column (optional, defaults to row count)
- `date_filter`: Date filter string (e.g., "< 2025-01-01")
- `min_observations`: Minimum time periods required
- `min_total_count`: Minimum total count threshold
- `decline_window_quarters`: Filter entities inactive >N quarters
- `temporal_granularity`: "yearly", "quarterly", or "semiannual"
- `vcp_p`: Random effects prior scale (default: 3.5)
- `fe_p`: Fixed effects prior scale (default: 3.0)

**Returns:**
- `results`: DataFrame with entity, Random_Intercept, Random_Slope, count, quadrant
- `stats`: Dictionary with model statistics

---

## Tracking Functions

### track_cumulative_movement

```python
from priorityx.tracking.movement import track_cumulative_movement

movement, meta = track_cumulative_movement(
    df,
    entity_col,
    timestamp_col,
    quarters=None,
    min_total_count=20,
    decline_window_quarters=6,
    temporal_granularity="quarterly",
    vcp_p=3.5,
    fe_p=3.0
)
```

Tracks entity movement through priority quadrants over time.

**Returns:**
- `movement`: DataFrame with quarterly X/Y positions
- `meta`: Dictionary with tracking metadata

### extract_transitions

```python
from priorityx.tracking.transitions import extract_transitions

transitions = extract_transitions(
    movement_df,
    focus_risk_increasing=True
)
```

Extracts quadrant transitions from movement data.

**Returns:**
- DataFrame with transition details and risk levels

---

## Visualization Functions

### plot_priority_matrix

```python
from priorityx.viz.matrix import plot_priority_matrix

fig = plot_priority_matrix(
    results_df,
    entity_name="Entity",
    figsize=(16, 12),
    top_n_labels=5,
    show_quadrant_labels=False,
    save_plot=False,
    output_dir="plot"
)
```

Creates scatter plot of priority matrix.

### plot_transition_timeline

```python
from priorityx.viz.timeline import plot_transition_timeline

fig = plot_transition_timeline(
    transitions_df,
    entity_name="Entity",
    filter_risk_levels=["critical", "high"],
    max_entities=20,
    save_plot=False,
    output_dir="plot"
)
```

Creates timeline heatmap of transitions.

### plot_movement_trajectories

```python
from priorityx.viz.trajectory import plot_movement_trajectories

fig = plot_movement_trajectories(
    movement_df,
    entity_name="Entity",
    max_entities=10,
    save_plot=False,
    output_dir="plot"
)
```

Creates trajectory plot showing movement through priority space.

---

## Utility Functions

### Display Summaries

```python
from priorityx.utils.helpers import display_quadrant_summary, display_transition_summary

display_quadrant_summary(results_df, entity_name="Service")
display_transition_summary(transitions_df, entity_name="Service")
```

Prints formatted summaries of analysis results.
