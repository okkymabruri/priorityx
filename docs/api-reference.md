# API Reference

## Core Functions

### fit_priority_matrix

```python
import priorityx as px

# Default: volume × growth (single GLMM)
results, stats = px.fit_priority_matrix(
    df,
    entity_col="service",
    timestamp_col="date",
    temporal_granularity="quarterly",
)
# Returns: entity, x_score, y_score, count, quadrant

# Custom Y axis: volume × resolution_days (two GLMMs)
results, stats = px.fit_priority_matrix(
    df,
    entity_col="service",
    timestamp_col="date",
    y_metric="resolution_days",
)

# Custom both axes with Gamma family for right-skewed data
results, stats = px.fit_priority_matrix(
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

**Returns:**
- `results`: DataFrame with `entity`, `x_score`, `y_score`, `count`, `quadrant`
- `stats`: Dictionary with model statistics

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

### track_cumulative_movement

```python
import priorityx as px

movement, meta = px.track_cumulative_movement(
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

analysis = px.extract_transition_drivers(
    movement_df,
    df_raw,
    entity_name="Service A",
    quarter_from="2024-Q2",
    quarter_to="2024-Q3",
    entity_col="service",
    timestamp_col="date",
    subcategory_cols=["type", "category"],  # Optional override; auto-detected if omitted
    top_n_subcategories=5,
    min_subcategory_delta=2,
)
```

Analyzes root causes of a quadrant transition.

**Parameters:**
- `movement_df`: Output from track_cumulative_movement()
- `df_raw`: Raw event data (pandas DataFrame)
- `entity_name`: Entity to analyze
- `quarter_from`: Starting quarter (e.g., "2024-Q2")
- `quarter_to`: Ending quarter (e.g., "2024-Q3")
- `entity_col`: Entity column name
- `timestamp_col`: Timestamp column name
- `subcategory_cols`: Optional list of subcategory columns (auto-detected when omitted)
- `top_n_subcategories`: Limit of subcategory drivers (default: 3)
- `min_subcategory_delta`: Minimum delta required for subcategory inclusion (default: 1)

**Returns:**
- Dictionary with:
  - `transition`: includes risk-level change and `is_concerning` flag
  - `magnitude`: cumulative deltas plus period-specific weekly averages and complaint counts
  - `spike_drivers`: summary notes aligned with spike indicators (`*X`, `*Y`, `*XY`)
  - `subcategory_drivers`: per-column driver lists obeying the provided knobs
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

fig = px.plot_priority_matrix(
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
import priorityx as px

fig = px.plot_transition_timeline(
    transitions_df,
    entity_name="Entity",
    filter_risk_levels=["critical", "high"],
    max_entities=20,
    save_plot=False,
    output_dir="plot",
    movement_df=movement_df
)
```

Creates timeline heatmap of transitions. Passing `movement_df` is required to compute the Crisis/Investigate/Monitor/Low priority tiers and spike markers (`*X`, `*Y`, `*XY`). Omitting it falls back to legacy risk-level tags.

### plot_entity_trajectories

```python
import priorityx as px

fig = px.plot_entity_trajectories(
    movement_df,
    entity_name="Entity",
    max_entities=10,
    save_plot=False,
    output_dir="plot"
)
```

Creates trajectory plot showing entity paths through priority space.

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
from priorityx.tracking.drivers import display_transition_drivers

display_transition_drivers(analysis)
```

Prints transition driver analysis in human-readable format.

**Parameters:**
- `analysis`: Output from extract_transition_drivers()
