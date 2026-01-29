# API Reference

## Core Functions

### fit_priority_matrix

```python
import priorityx as px

# Default: volume × growth (single GLMM) - simple form
results = px.fit_priority_matrix(
    df,
    entity_col="service",
    timestamp_col="date",
    temporal_granularity="quarterly",
)
# Returns: DataFrame with entity, x_score, y_score, count, quadrant

# Get statistics too (advanced)
results, stats = px.fit_priority_matrix(
    df,
    entity_col="service",
    timestamp_col="date",
    temporal_granularity="quarterly",
    return_stats=True,  # returns (DataFrame, dict) tuple
)

# Custom Y axis: volume × resolution_days (two GLMMs)
results = px.fit_priority_matrix(
    df,
    entity_col="service",
    timestamp_col="date",
    y_metric="resolution_days",
)

# Custom both axes with Gamma family for right-skewed data
results = px.fit_priority_matrix(
    df,
    entity_col="service",
    timestamp_col="date",
    x_metric="disputed_amount",
    y_metric="paid_amount",
    family="gamma",
)
```

Unified entry point for GLMM-based entity prioritization. Supports count-based (Poisson) and metric-based (Gaussian/Gamma) axes.

**Parameters:**

- `df`: pandas DataFrame with one row per event
- `entity_col`: Entity identifier column name
- `timestamp_col`: Date column name
- `x_metric`: Optional metric column for X axis (None = count-based)
- `y_metric`: Optional metric column for Y axis (None = count-based)
- `x_effect`: Random effect for X score ("intercept" or "slope", default: "intercept")
- `y_effect`: Random effect for Y score ("intercept" or "slope", default: "slope")
- `family`: Distribution for continuous metrics ("gaussian" or "gamma", default: "gaussian")
- `count_col`: Optional count column (default: row count per entity-period)
- `date_filter`: Date filter string (e.g., "< 2025-01-01", ">= 2024-01-01")
- `min_observations`: Minimum time periods required per entity
- `min_total_count`: Minimum total count threshold
- `decline_window_quarters`: Filter entities inactive >N quarters
- `temporal_granularity`: "yearly", "quarterly", "semiannual", or "monthly"
- `vcp_p`: Random effects prior scale (default: 3.5)
- `fe_p`: Fixed effects prior scale (default: 3.0)
- `return_stats`: If True, returns (DataFrame, dict) tuple (default: False)

**Returns:**

- Default (`return_stats=False`): DataFrame with `entity`, `x_score`, `y_score`, `count`, `quadrant`
- With `return_stats=True`: Tuple of (DataFrame, stats dict)

**Family Selection:**

- `"gaussian"` (default): Works for any data, robust for entity ranking
- `"gamma"`: Use for right-skewed positive data (durations, monetary amounts)

> **Reproducibility:** set the environment variable `PRIORITYX_GLMM_SEED` or call `set_glmm_random_seed(value)` before invoking `fit_priority_matrix` to obtain deterministic variational Bayes estimates.

---

## Metrics Functions

### aggregate_entity_metrics

```python
import priorityx as px

metrics = px.aggregate_entity_metrics(
    df,
    entity_col="service",
    duration_start_col="opened_at",
    duration_end_col="closed_at",
    primary_col="exposure",
    secondary_col="recovery",
)
# Returns: entity, mean_duration, total_primary, total_secondary, secondary_to_primary_ratio
```

Computes per-entity aggregated metrics for enrichment.

### add_priority_indices

```python
import priorityx as px

enriched = px.add_priority_indices(
    results,
    volume_col="count",
    growth_col="y_score",
    severity_col="total_primary",
    resolution_col="mean_duration",
    recovery_col="secondary_to_primary_ratio",
    # Weights (defaults shown)
    w_volume=0.4, w_growth=0.4, w_severity=0.2,
    w_resolution=0.5, w_recovery=0.5,
    w_risk=0.7, w_quality=0.3,
)
```

Adds composite risk indices to enriched entity data.

**Output columns:**

- `z_volume`, `z_growth`, `z_severity`: Z-scored risk components
- `z_neg_resolution`, `z_recovery`: Z-scored quality components
- `RI`: Risk Index = weighted sum of z_volume, z_growth, z_severity
- `SQI`: Service Quality Index = weighted sum of z_neg_resolution, z_recovery
- `EWI`: Early Warning Index = w_risk × RI + w_quality × (-SQI)

**Usage:**
```python
# Top priority entities
top_risks = enriched.nlargest(10, "EWI")
```

### sensitivity_analysis

```python
import priorityx as px

results = px.sensitivity_analysis(
    df,
    index_col="EWI",
    entity_col="entity",
    weight_ranges={
        "w_risk": [0.6, 0.7, 0.8],
        "w_quality": [0.2, 0.3, 0.4],
    },
    top_n=10,
)
```

Tests ranking stability across weight variations.

---

## Tracking Functions

### track_movement

```python
import priorityx as px

# Simple form (most users)
movement = px.track_movement(
    df,
    entity_col="service",
    timestamp_col="date",
    quarters=None,
    min_total_count=20,
    temporal_granularity="quarterly",
)

# Get metadata too (advanced)
movement, meta = px.track_movement(
    df,
    entity_col="service",
    timestamp_col="date",
    min_total_count=20,
    temporal_granularity="quarterly",
    return_metadata=True,  # returns (DataFrame, dict) tuple
)
```

Tracks entity movement through priority quadrants over time.

**Parameters:**

- `df`: Input pandas DataFrame
- `entity_col`: Entity identifier column name
- `timestamp_col`: Date column name
- `quarters`: Period specification (None = auto-detect)
- `min_total_count`: Minimum total count for inclusion (default: 20)
- `decline_window_quarters`: Max quarters after last observation (default: 6)
- `temporal_granularity`: "quarterly" or "monthly"
- `vcp_p`: Random effects prior scale (default: 3.5)
- `fe_p`: Fixed effects prior scale (default: 3.0)
- `return_metadata`: If True, returns (DataFrame, dict) tuple (default: False)

**Returns:**

- Default (`return_metadata=False`): DataFrame with quarterly X/Y positions
- With `return_metadata=True`: Tuple of (DataFrame, metadata dict)

### load_or_track_movement

```python
import priorityx as px

# Simple form - compute or load from cache
movement = px.load_or_track_movement(
    df,
    entity_name="issue",
    entity_col="service",
    timestamp_col="date",
    quarters=["2024-01-01", "2025-01-01"],
    min_total_count=20,
    output_dir="results/csv",
)

# Get CSV path for logging
movement, csv_path = px.load_or_track_movement(
    df,
    entity_name="issue",
    entity_col="service",
    timestamp_col="date",
    quarters=["2024-01-01", "2025-01-01"],
    min_total_count=20,
    output_dir="results/csv",
    return_path=True,
)
```

Caches movement tracking results to disk. On subsequent runs, loads from
cache if available (`use_cache=True` by default).

**Parameters:**

- `df`: Input DataFrame
- `entity_name`: Friendly name for file naming
- `entity_col`: Entity column name
- `timestamp_col`: Timestamp column name
- `quarters`: Period specification
- `min_total_count`: Minimum count threshold
- `temporal_granularity`: "quarterly" or "monthly" (default: "quarterly")
- `output_dir`: Cache directory (default: "results/csv")
- `use_cache`: Load from cache if available (default: True)
- `return_path`: If True, returns (DataFrame, csv_path) tuple (default: False)

**Returns:**

- Default (`return_path=False`): DataFrame with movement data
- With `return_path=True`: Tuple of (DataFrame, csv_path)

### extract_transitions

```python
import priorityx as px

transitions = px.extract_transitions(
    movement_df,
    focus_risk_increasing=True
)
```

Extracts quadrant transitions from movement data.

**Returns:**

- DataFrame with transition details and risk levels

### extract_transition_drivers

```python
import priorityx as px

# Basic usage with categorical breakdowns
analysis = px.extract_transition_drivers(
    movement_df,
    df_raw,
    entity_name="Service A",
    period_from="2024-Q2",
    period_to="2024-Q3",
    entity_col="service",
    timestamp_col="date",
    subcategory_cols=["type", "category"],  # categorical breakdowns
)

# With numeric column breakdowns (amounts, durations)
analysis = px.extract_transition_drivers(
    movement_df,
    df_raw,
    entity_name="Fintech - Pinjaman Online",
    period_from="2024-Q3",
    period_to="2024-Q4",
    entity_col="product",
    timestamp_col="date",
    subcategory_cols=["region", "gender"],
    numeric_cols={
        "disputed_amount": [0, 1e6, 5e6, 10e6],  # explicit bin edges
        "resolution_days": 4,                     # 4 quantile bins (auto)
    },
)
```

Analyzes root causes of a quadrant transition.

**Parameters:**

- `movement_df`: Output from track_movement()
- `df_raw`: Raw event data (pandas DataFrame)
- `entity_name`: Entity to analyze
- `period_from`: Starting period (e.g., "2024-Q2", "2024-01")
- `period_to`: Ending period (e.g., "2024-Q3", "2024-02")
- `entity_col`: Entity column name
- `timestamp_col`: Timestamp column name
- `subcategory_cols`: Optional list of categorical columns for breakdown (auto-detected when omitted)
- `numeric_cols`: Optional dict of numeric columns with bin specs:
  - List of floats: explicit bin edges (e.g., `[0, 1e6, 5e6, 10e6]`)
  - Integer: number of quantile bins (e.g., `4` for quartiles)
- `top_n`: Limit of drivers per column (default: 3)
- `min_delta`: Minimum count delta for inclusion (default: 1)

**Returns:**

- Dictionary with:
  - `transition`: includes risk-level change and `is_concerning` flag
  - `magnitude`: cumulative deltas plus period-specific weekly averages and complaint counts
  - `spike_drivers`: summary notes aligned with spike indicators (`*X`, `*Y`, `*XY`)
  - `subcategory_drivers`: per-column driver lists for categorical columns
  - `numeric_drivers`: per-column driver lists for numeric columns (with bin edges)
  - `priority`: priority tier, trigger reason, spike axis
  - `meta`: diagnostic flags (e.g., whether subcategory columns were auto-detected)

### classify_priority

```python
from priorityx.tracking.drivers import classify_priority

priority, reason, spike_axis = classify_priority(
    from_quadrant="Q3",
    to_quadrant="Q1",
    x=0.5, y=0.6,
    x_delta=0.5, y_delta=0.5,
    count_delta=100,
    percent_change=200
)
```

Classifies supervisory priority (1=Critical, 2=Investigate, 3=Monitor, 4=Low).

**Returns:**

- Tuple of (priority, reason, spike_axis)

---

## Visualization Functions

### plot_priority_matrix

```python
import priorityx as px
from pathlib import Path

# Basic plot (no save)
fig = px.plot_priority_matrix(
    results_df,
    entity_name="Entity",
    figsize=(16, 12),
    top_n_labels=5,
    show_quadrant_labels=False,
)

# Save to file with simplified path API
PLOT_DIR = Path("results/plot")
CSV_DIR = Path("results/csv")

fig = px.plot_priority_matrix(
    results_df,
    entity_name="issue",
    plot_path=PLOT_DIR / "priority_matrix.png",  # Path or str
    csv_path=CSV_DIR / "priority_matrix.csv",    # Path or str
    close_fig=True,
)
```

Creates scatter plot of priority matrix.

**Path Parameters:**

- `plot_path`: Path to save plot (accepts Path or str). If provided, saves plot.
- `csv_path`: Path to save CSV (accepts Path or str). If provided, saves CSV.

### plot_transition_timeline

```python
import priorityx as px
from pathlib import Path

# Basic plot
fig = px.plot_transition_timeline(
    transitions_df,
    entity_name="Entity",
    filter_risk_levels=["critical", "high"],
    max_entities=20,
    movement_df=movement_df,
)

# Save with simplified path API
fig = px.plot_transition_timeline(
    transitions_df,
    entity_name="issue",
    filter_risk_levels=["critical", "high"],
    max_entities=20,
    movement_df=movement_df,
    plot_path=PLOT_DIR / "transitions.png",
    csv_path=CSV_DIR / "transitions.csv",
    close_fig=True,
)
```

Creates timeline heatmap of transitions. Passing `movement_df` is required to compute the Crisis/Investigate/Monitor/Low priority tiers and spike markers (`*X`, `*Y`, `*XY`). Omitting it falls back to legacy risk-level tags.

**Path Parameters:**

- `plot_path`: Path to save plot (accepts Path or str). If provided, saves plot.
- `csv_path`: Path to save CSV (accepts Path or str). If provided, saves CSV.

### plot_entity_trajectories

```python
import priorityx as px
from pathlib import Path

# Basic usage (no save)
fig = px.plot_entity_trajectories(
    movement_df,
    entity_name="Entity",
    max_entities=10,
)

# Auto-select top movers with simplified path API (recommended)
fig = px.plot_entity_trajectories(
    movement_df,
    entity_name="product",
    highlight_top_n=4,                   # auto-select top 4 entities
    highlight_by="trajectory_distance",  # by path length (or "total_movement")
    recent_periods=6,                    # limit to last 6 periods
    plot_path=PLOT_DIR / "trajectories.png",
    csv_path=CSV_DIR / "trajectories.csv",
    close_fig=True,
)
```

Creates trajectory plot showing entity paths through priority space.

**Parameters:**

- `movement_df`: Output from track_movement()
- `entity_name`: Label for entity type (e.g., "product", "service")
- `max_entities`: Maximum entities to show (default: 10)
- `highlight_entities`: List of specific entities to highlight
- `highlight_top_n`: Auto-select top N entities by movement (overrides max_entities)
- `highlight_by`: Selection method when using highlight_top_n:
  - `"trajectory_distance"`: Euclidean path length (sum of sqrt(dx² + dy²))
  - `"total_movement"`: Manhattan distance (sum of |dx| + |dy|)
- `recent_periods`: Limit trajectory to last N periods (useful for long histories)
- `temporal_granularity`: "quarterly", "monthly", etc.
- `plot_path`: Path to save plot (accepts Path or str). If provided, saves plot.
- `csv_path`: Path to save CSV (accepts Path or str). If provided, saves CSV.
- `close_fig`: Close figure after rendering (set True for Jupyter to avoid duplicates)

---

## Utility Functions

### Display Summaries

```python
from priorityx.utils.helpers import (
    display_quadrant_summary,
    display_transition_summary,
    display_movement_summary
)

display_quadrant_summary(results_df, entity_name="Service")
display_transition_summary(transitions_df, entity_name="Service")
display_movement_summary(movement_df, entity_name="Service")
```

Prints formatted summaries of analysis results.

### display_transition_drivers

```python
import priorityx as px

# Print to console
px.display_transition_drivers(analysis)

# Print and save to file
px.display_transition_drivers(
    analysis,
    save_txt=True,
    txt_path="driver_analysis.txt",
    txt_mode="a",  # append (default) or "w" to overwrite
)
```

Prints transition driver analysis in human-readable format.

**Parameters:**

- `analysis`: Output from extract_transition_drivers()
- `save_txt`: Save output to text file (default: False)
- `txt_path`: Path for text file (required if save_txt=True)
- `txt_mode`: File mode - "a" to append (default), "w" to overwrite
