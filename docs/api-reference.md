# API Reference

The examples below assume your prepared event DataFrame is `df`. Fitting returns
`results`; tracking returns `movement` (called `movement_df` in plot examples).
See the [quickstart](quickstart.md) for a connected workflow and
[AutoViz example](autoviz-example.md) for saved data you can open without fitting.

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

# Custom Y axis: count level × resolution-duration trend (two GLMMs)
results = px.fit_priority_matrix(
    df,
    entity_col="service",
    timestamp_col="date",
    y_metric="resolution_days",
    temporal_granularity="quarterly",
)

# Compare metric levels with Gamma models for strictly positive data
results = px.fit_priority_matrix(
    df,
    entity_col="service",
    timestamp_col="date",
    x_metric="disputed_amount",
    y_metric="paid_amount",
    family="gamma",
    y_effect="intercept",
    temporal_granularity="quarterly",
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
- `count_col`: Optional column summed as the count response in count-model axes; omitted means row counts. Returned `count` and `min_total_count` still use event rows. Different axis metrics trigger separate models, and a count axis respects this column.
- `date_filter`: Date filter string (e.g., "< 2025-01-01", ">= 2024-01-01")
- `min_observations`: Minimum observed entity-period rows (argument default: 3). A value of 3 becomes 8 for Quarterly and 4 for Semiannual; Monthly/Yearly retain 3.
- `min_total_count`: Minimum event rows per entity (default: 0)
- `decline_window_quarters`: Quarterly-only inactivity window, approximately 91 days per quarter (default: 6; non-positive disables)
- `temporal_granularity`: "yearly" (default), "quarterly", "semiannual", or "monthly"
- `vcp_p`: Random effects prior scale (default: 3.5)
- `fe_p`: Fixed effects prior scale (default: 3.0)
- `return_stats`: If True, returns (DataFrame, dict) tuple (default: False)

**Returns:**

- Default (`return_stats=False`): DataFrame with `entity`, `x_score`, `y_score`, `count`, `quadrant`
- With `return_stats=True`: Tuple of (DataFrame, stats dict)

**Family Selection:**

- `"gaussian"` (default): Continuous metric means with a Gaussian response model
- `"gamma"`: Continuous positive metric means with a Gamma/log-link response model; non-positive aggregated values are excluded

Count-based axes always use Poisson. Metric-based random effects are
z-standardized across fitted entities. Different metrics use separate fits;
`x_effect` and `y_effect` still select the requested effects. See
[methodology](methodology.md) for score interpretation and filtering limits.

Set `PRIORITYX_GLMM_SEED` before starting Python, or call
`px.set_glmm_random_seed(value)` before fitting, for repeatability in a fixed
data/software environment. It does not promise identical estimates across versions
or platforms. `return_stats=True` reports the estimator method actually used.

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
# Identity column remains "service"; optional metric columns depend on inputs.
```

Computes per-entity aggregated metrics for enrichment.
`mean_duration` uses whole non-negative days between the supplied timestamps;
the magnitude columns are summed. The ratio is missing when the primary total
is not positive. Merge on the actual identity column before calculating indices:

```python
enriched_input = results.merge(
    metrics.rename(columns={"service": "entity"}), on="entity", how="left"
)
```

### add_priority_indices

```python
import priorityx as px

enriched = px.add_priority_indices(
    enriched_input,
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
- `RI`: Weighted combination of available risk components
- `SQI`: Weighted combination of available quality components; higher is better
- `EWI`: Weighted combination of RI and negative SQI; higher is higher priority

Weights are normalized over available components at each stage. With all mapped
columns present and the default weights shown, EWI is `0.7 * RI - 0.3 * SQI`.
Unavailable columns are omitted, and a stage with no components is not created.
Constant components have zero z-scores. These indices are relative scores,
not calibrated probabilities.

**Usage:**
```python
# Top priority entities
top_risks = enriched.nlargest(10, "EWI")
```

### sensitivity_analysis

```python
from priorityx.metrics import sensitivity_analysis

stability = sensitivity_analysis(
    results,  # fitted matrix with entity, count and y_score
    index_col="EWI",
    entity_col="entity",
    weight_variations=[
        {"w_volume": 0.6, "w_growth": 0.4},
        {"w_volume": 0.4, "w_growth": 0.6},
    ],
    top_n=5,
)
```

Tests ranking stability across weight variations.
Import from `priorityx.metrics` (also available from `priorityx.api`); it is not
re-exported as `px.sensitivity_analysis` at the package root.

- `index_func`: Callable accepting the input table and weight keywords, returning
  a table with `entity_col` / `index_col`; defaults to `add_priority_indices`.
- `weight_variations`: Explicit `list[dict]` of weight keyword arguments. When
  omitted, four built-in volume/growth/severity combinations are used.
- `top_n`: Size of each top group (default 10); `entity_col` defaults to `entity`
  and `index_col` to `EWI`.
- Output: `variation`, string `weights` and ordered `top_entities`. Multiple
  usable variations also include `core_overlap` (membership in every top group)
  and `stable_overlap` (membership in at least half). These are set-overlap
  counts, not a rank-correlation statistic. Variations missing the index column
  are skipped; no usable variations gives an empty DataFrame.

When testing quality or severity weights, provide the corresponding source
columns and an `index_func` that maps them into `add_priority_indices`.

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
- `decline_window_quarters`: Endpoint inactivity window of approximately 91 days per quarter (default: 6), including for Monthly tracking
- `temporal_granularity`: "quarterly" or "monthly"
- `vcp_p`: Random effects prior scale (default: 3.5)
- `fe_p`: Fixed effects prior scale (default: 3.0)
- `return_metadata`: If True, returns (DataFrame, dict) tuple (default: False)

**Returns:**

- Default (`return_metadata=False`): DataFrame with cumulative X/Y positions and the canonical `quarter` column for both cadences (`YYYY-Qn` or `YYYY-MM`)
- With `return_metadata=True`: Tuple of (DataFrame, metadata dict)

`quarters` can be `None`, a two-date range with exclusive end boundary, or a
list of `(period_label, exclusive_cutoff_date)` tuples. Quarterly ranges require
quarter starts; Monthly ranges require month starts. For example, Monthly
`quarters=["2025-01-01", "2026-01-01"]` covers January–December 2025.
The global baseline uses the full supplied input; filter input separately when
later observations must be excluded. Period fits below 100 cumulative rows or
with fitting errors are skipped. Deltas then compare successive available rows.
Metadata retains `quarter_schedule` / `quarters_analyzed` names for both cadences.

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

Caches movement tracking results by a 16-character input/settings fingerprint
(`use_cache=True` by default). Repeating a request reuses its exact CSV without
fitting or rewriting it. Changing the supplied data, column mapping, period
schedule, thresholds, priors, inactivity window, effective GLMM seed or package
version creates a different file and preserves the previous result.
The fingerprint includes all supplied values, columns, dtypes, index and order;
even an unused column can invalidate it. Apply source filters before calling the
wrapper; their resulting DataFrame is fingerprinted. Equivalent normalized
period schedules share a key.

`use_cache=False` explicitly recomputes and atomically replaces only that
request's file. Failed fitting or saving preserves existing output. Old date-only
CSVs are ignored and left unchanged, so the first call after upgrading may fit
again. An unreadable keyed CSV raises `ValueError` with recomputation guidance.
No manifest or run history is written. See [output naming](output_naming.md).

**Parameters:**

- `df`: Input DataFrame
- `entity_name`: Friendly name for file naming
- `entity_col`: Entity column name
- `timestamp_col`: Timestamp column name
- `quarters`: Period specification
- `min_total_count`: Minimum count threshold
- `decline_window_quarters`: Inactivity window forwarded to tracking (default: 6)
- `temporal_granularity`: "quarterly" or "monthly" (default: "quarterly")
- `vcp_p`: Random effects prior scale (default: 3.5)
- `fe_p`: Fixed effects prior scale (default: 3.0)
- `output_dir`: Cache directory (default: "results/csv")
- `use_cache`: Load from cache if available (default: True)
- `return_path`: If True, returns (DataFrame, csv_path) tuple (default: False)

These prior/inactivity settings are forwarded unchanged to `track_movement()`.
Set a fixed seed with `set_glmm_random_seed()` for repeatable refits; a cache hit
reopens previously saved estimates. The key identifies the analysis request and
does not detect manual edits to otherwise readable output values.

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

The canonical input period column is `quarter` for Monthly too; a result loaded
directly from a Monthly `month` CSV must be renamed before using this analysis
function. Output uses `transition_quarter` in both cadences. An event-free result
can be an empty DataFrame without columns; give it the required empty schema before
AutoViz import. Extraction thresholds differ from display-class thresholds;
see [priority classification](priority_classification.md).

### extract_transition_drivers

```python
import priorityx as px

# Basic usage with categorical breakdowns
analysis = px.extract_transition_drivers(
    movement_df,
    df_raw,
    entity_name="Entity A",
    period_from="2024-Q2",
    period_to="2024-Q3",
    entity_col="entity",
    timestamp_col="date",
    subcategory_cols=["type", "category"],  # categorical breakdowns
)

# With numeric column breakdowns (amounts, durations)
analysis = px.extract_transition_drivers(
    movement_df,
    df_raw,
    entity_name="Entity B",
    period_from="2024-Q3",
    period_to="2024-Q4",
    entity_col="entity",
    timestamp_col="date",
    subcategory_cols=["region", "gender"],
    numeric_cols={
        "disputed_amount": [0, 1e6, 5e6, 10e6],  # explicit bin edges
        "resolution_days": 4,                     # 4 quantile bins (auto)
    },
)
```

Summarizes associated count changes across supplied categories and numeric bins.
These descriptive breakdowns do not identify causal effects.

**Parameters:**

- `movement_df`: Output from track_movement()
- `df_raw`: Raw event data (pandas DataFrame)
- `entity_name`: Entity to analyze
- `period_from`: Saved Quarterly movement label (e.g., "2024-Q2"); see the window limitation below
- `period_to`: Saved Quarterly movement label (e.g., "2024-Q3"); Monthly labels are not supported by the current driver date conversion
- `entity_col`: Entity column name
- `timestamp_col`: Timestamp column name
- `subcategory_cols`: Optional list of categorical columns for breakdown (auto-detected when omitted)
- `numeric_cols`: Optional dict of numeric columns with bin specs:
  - List of floats: explicit bin edges (e.g., `[0, 1e6, 5e6, 10e6]`)
  - Integer: number of quantile bins (e.g., `4` for quartiles)
- `top_n`: Limit of drivers per column (default: 5)
- `min_delta`: Minimum count delta for inclusion (default: 2)

**Returns:**

- Dictionary with:
  - `transition`: includes risk-level change and `is_concerning` flag
  - `magnitude`: cumulative deltas plus raw-window event counts and weekly averages using a fixed 13-week divisor
  - `spike_drivers`: summary notes aligned with spike indicators (`*X`, `*Y`, `*XY`)
  - `subcategory_drivers`: per-column driver lists for categorical columns
  - `numeric_drivers`: per-column driver lists for numeric columns (with bin edges)
  - `priority`: priority tier, trigger reason, spike axis
  - `meta`: diagnostic flags (e.g., whether subcategory columns were auto-detected)

Categorical/numeric driver keys are present when their analyses run. An omitted
`subcategory_cols` list enables auto-detection; an empty list disables category
breakdowns, and unknown explicit columns raise `ValueError`. Inspect
`meta["subcategory_columns_used"]` and `meta["subcategory_columns_auto_detected"]`.
Numeric bins describe within-bin event counts, not the sum of the metric.

Driver contribution percentages use the **net difference between the two raw
period totals**. For a net increase of 20, a category increase of 30 contributes
150% and a decrease of 10 contributes -50%. Percentages may exceed 100% and are
`None` when the net change is zero. The text summary prints “not defined”.
Existing `top_drivers` lists contain increases; additive `top_decreases` lists
contain decreases ranked by magnitude. Each list respects `top_n` and `min_delta`.
The retained `top_n_explain_pct` key gives the increases' combined percentage of
net change; `top_n_decrease_pct` gives the decreases' combined percentage.
`top_n_increase_coverage_pct` and `top_n_decrease_coverage_pct` separately give
the share of all positive or negative deltas covered by each truncated list.
`percentage_denominator`, `percentage_defined`, period counts and reconciliation
metadata make that distinction explicit. Do not sum percentages across dimensions.
Numeric results report per-period missing, nonfinite and outside-bin exclusions,
so included-bin deltas plus excluded-count deltas reconcile to the net change. Missing
categories remain a separate `None` value; caller labels are not rewritten.

Explicit category/numeric column names and bin edges are validated. Movement
inputs with duplicate entity-period rows are rejected rather than choosing one
arbitrarily. Bin labels use inclusive/exclusive interval notation matching the
actual shared bins across both periods.
Constant numeric data use one singleton interval `[value, value]`; tied quantiles
can reduce the requested number of bins. Declines use the same signed net-change
formula, so a decreasing category contributes positively to an overall decline.

#### Driver period windows

The raw-event windows match the calendar meaning of the saved movement labels:

| Saved movement label | Raw-event window, inclusive start / exclusive end |
|---|---|
| `2024-Q1` | 2024-01-01 to 2024-04-01 |
| `2024-Q2` | 2024-04-01 to 2024-07-01 |
| `2024-Q3` | 2024-07-01 to 2024-10-01 |
| `2024-Q4` | 2024-10-01 to 2025-01-01 |

The reported weekly averages still divide by 13. Monthly labels raise
`ValueError` in this conversion. Driver breakdowns remain descriptive event
counts, not causal explanations of score changes; they do not change saved
movement scores or AutoViz layouts.

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

Classifies driver-analysis priority (1=Critical, 2=Investigate, 3=Monitor, 4=Low).
The timeline uses the separate `tracking.transitions` helper, whose numeric class
1 is labeled Crisis. [Classification rules](priority_classification.md) explain
the strict comparisons, suffixes and distinction from saved `risk_level`.

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
`results_df` uses `entity`, `x_score`, `y_score`, `count` and `quadrant` (or
explicit `x_col` / `y_col` mappings), rather than legacy random-effect names.

Pass `language="id"` for Indonesian titles, axes and legends. English is the
default. Caller-provided titles and axis labels, entity names, saved values and
machine-readable quadrant codes remain unchanged.

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
PLOT_DIR = Path("results/plot")
CSV_DIR = Path("results/csv")
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

Creates a timeline of transitions. Passing `movement_df` computes the
Crisis/Investigate/Monitor/Low event classes and spike markers (`*X`, `*Y`,
`*XY`). Without movement data, the existing default is Investigate. These
algorithmic classes are not verified distress.
Keep full movement history in original chronological order for class calculation.
`filter_risk_levels` filters saved `risk_level`, not computed event class.
The original plotting API does not impose AutoViz's YTD display window.

`language="id"` translates the chart text and event-class legend while keeping
the transition data, `Q1`–`Q4` codes, risk keys and `*X`/`*Y`/`*XY` suffixes.

`entity_name` is a caller-provided display label. It is used unchanged for the
entity axis and generated title; PriorityX does not infer a domain from its text.

**Label styles:**

- `label_style="compact"` (default): `3→②`, with the destination digit
  inside the colored event marker and spike indicators after it: `3→②*XY`.
  The notation stays horizontal and always reads left to right, including at
  plot edges. Markers are 14 pt in diameter; event text remains 12 pt.
  The default canvas is **21×12 inches**, allowing more space between events.
- `label_style="quadrant"`: retain `Q3→Q2` and 10 pt markers, using the same
  measured placement and leader lines as before, on a **16×12-inch** default canvas.

An explicit `figsize=(width, height)` overrides either default; the renderer
does not enlarge it automatically when labels cannot fit.
`figsize` is measured in inches; export `dpi` controls resolution independently.
For example, use `figsize=(24, 12)` for a wider canvas while keeping the same
font sizes. Increasing DPI alone does not add room between labels.

```python
# Restore the Q-style display used before the compact default.
fig = px.plot_transition_timeline(
    transitions_df, movement_df=movement_df, label_style="quadrant"
)
```

The compact key shows a reading example drawn from a displayed event, the color
legend and the `*X`, `*Y`, `*XY` suffix definitions. It intentionally keeps the
key compact: the chart does not repeat the quadrant sign table or an outcome
disclaimer. The example is explanatory; it adds no event marker to the data
axes. Numbers identify score quadrants **at the event**, rather than ranks,
calendar quarters or current status. Color encodes the event class independently
of the destination quadrant. Both styles retain the origin,
destination and spike indicators; only annotation text moves during layout.
Unknown quadrant codes retain their full transition labels with a warning in
compact mode. An unsupported `label_style` raises `ValueError`.

**Path Parameters:**

- `plot_path`: Path to save plot (accepts Path or str). If provided, saves plot.
- `csv_path`: Path to save CSV (accepts Path or str). If provided, saves CSV.

### layout_transition_labels

Transition timelines use rendered text and marker dimensions. Compact labels
stay beside their markers with the suffix on the right; measured empty padding
at plot edges preserves their reading order. Q-style label centers stay nearest
their entity row, with leader lines when displaced. Selection, ordering, event dates,
marker data coordinates, date ticks and classifications are unchanged.

If you customize a timeline, rerun placement **after** your final layout changes:

```python
fig = px.plot_transition_timeline(transitions_df, movement_df=movement_df)
# Apply custom ticks, title, legend, figsize or DPI here.
fig.set_dpi(300)  # Measure with the same renderer resolution used for export.
fig.tight_layout()
px.layout_transition_labels(fig)
fig.savefig("timeline.png", dpi=300, bbox_inches="tight")
```

The helper returns the same figure and repeated calls reset placement rather than
accumulating offsets. A `TransitionLabelLayoutWarning` means some labels could
not fit: all labels remain, but the chart needs review. Explicitly increase
`figsize` width for adjacent events or render separately selected `entity_filter`
pages for crowded rows. Compact notation stays inline even if space is
insufficient; a warning means the chart fails readability acceptance. The renderer never
shrinks text, removes events, changes date ticks or expands the canvas automatically.

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

# Auto-select top movers with explicit paths
PLOT_DIR = Path("results/plot")
CSV_DIR = Path("results/csv")
fig = px.plot_entity_trajectories(
    movement_df,
    entity_name="Entity",
    highlight_top_n=4,                   # auto-select top 4 entities
    highlight_by="trajectory_distance",  # by path length (or "total_movement")
    recent_periods=6,                    # limit to last 6 periods
    plot_path=PLOT_DIR / "trajectories.png",
    csv_path=CSV_DIR / "trajectories.csv",
    close_fig=True,
)
```

Creates trajectory plot showing entity paths through priority space.
The generated title uses the caller's `entity_name` unchanged.
This original helper selects up to ten entities by default; AutoViz's separate
default is three ranked trend-change paths. Its optional CSV contains only the
selected/retained plot rows; save full movement separately. With `period_count`,
the helper trims each path after its last positive-count period.
Saved tables may already contain `last_active_quarter`; the helper derives the
activity boundary without colliding with that metadata. The caller's full saved
table remains unchanged, and AutoViz uses the same saved history independently.
Pass `language="id"` for Indonesian axes, titles and quadrant legends without
changing trajectory coordinates or panel dimensions.

**Parameters:**

- `movement_df`: Output from track_movement()
- `entity_name`: Caller-provided label for the entity type
- `max_entities`: Maximum entities to auto-select (default: 10); an explicit nonempty `highlight_entities` list takes precedence without truncation
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

Timeline and trajectory helpers return `None` for empty selected inputs. Matrix
and nonempty timeline/trajectory calls return a Matplotlib figure. Original
`plot_path` writes PNG content; use `fig.savefig()` or the AutoViz print renderer
for SVG. See [saving and naming](output_naming.md) for path precedence and formats.

---

## Utility Functions

### Display Summaries

```python
from priorityx.utils.helpers import (
    display_quadrant_summary,
    display_transition_summary,
    display_movement_summary
)

display_quadrant_summary(results_df, entity_name="Entity")
display_transition_summary(transitions_df, entity_name="Entity")
display_movement_summary(movement_df, entity_name="Entity")
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
