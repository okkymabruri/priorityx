# Changelog

Only major releases (v0.x.0) are listed.

---

## v0.6.0 (2026-01)

**Simplified Visualization Path API**

- Added `plot_path` and `csv_path` parameters to `plot_priority_matrix()`, `plot_transition_timeline()`, `plot_entity_trajectories()`
- Path implies save: providing path automatically saves output
- Accepts Path objects directly (no `str()` wrapper needed)
- Old API (`save_plot=True` + `plot_dir` + `plot_filename`) deprecated

---

## v0.5.0 (2026-01)

**Simplified API Returns**

- Added `return_stats`, `return_metadata`, `return_path` parameters to core functions
- Functions now return just DataFrame by default; pass `return_*=True` for tuple
- Renamed `track_cumulative_movement()` → `track_movement()` (old name deprecated)
- Fixed threshold calibration docs and x_score/y_score interpretation

---

## v0.4.0 (2025-01)

**Unified API with Axis Metrics**

- Introduced `x_metric` / `y_metric` parameters to `fit_priority_matrix()` for flexible axis definitions beyond default volume/growth
- Added `x_score` / `y_score` coordinate-based quadrant classification (replaces Random_Intercept/Random_Slope naming in outputs)
- Added Gamma family support for continuous GLMM (e.g., duration or amount metrics)
- Gaussian GLMM support for metric-based axes
- Improved quadrant label rendering with configurable legend position (`legend_loc`, `show_legend`)
- Row-aligned quadrant label offsetting to avoid legend overlap

**Trajectory Auto-Selection**

- Added `highlight_top_n` parameter to `plot_entity_trajectories()` for automatic entity selection
- Added `highlight_by` parameter: `"trajectory_distance"` (euclidean path) or `"total_movement"` (manhattan)
- Added `recent_periods` parameter to limit trajectory window to last N periods

**Enhanced Driver Analysis**

- Added `numeric_cols` parameter to `extract_transition_drivers()` for amount/duration breakdowns
  - Explicit bins: `{"amount": [0, 1e6, 5e6, 10e6]}`
  - Auto quantiles: `{"duration": 4}` (4 bins)
- Renamed `quarter_from`/`quarter_to` to `period_from`/`period_to` (backwards compatible)
- Renamed `top_n_subcategories` to `top_n`, `min_subcategory_delta` to `min_delta` (backwards compatible)
- Added `save_txt`, `txt_path`, `txt_mode` parameters to `display_transition_drivers()` for file output

---

## v0.3.0 (2024-12)

**Entity Metrics and Priority Indices**

- Implemented `add_priority_indices()` for composite index calculation:
  - **RI** (Risk Index): volume + growth + severity
  - **SQI** (Service Quality Index): resolution speed + recovery rate
  - **EWI** (Early Warning Index): blends RI and SQI for prioritization
- Added `aggregate_entity_metrics()` helper for per-entity metric aggregation
- Added `sensitivity_analysis()` for weight stability testing
- Monthly granularity support (beta) in GLMM and visualizations
- Unified `px.*` namespace imports pattern

---

## v0.2.0 (2024-11)

**Transition Tracking and Visualization**

- Implemented `track_movement()` for entity trajectory tracking (originally `track_cumulative_movement`, renamed in v0.5.0)
- Added `extract_transitions()` for quadrant movement detection
- Transition timeline visualization with priority-based coloring (Crisis/Investigate/Monitor/Low)
- Spike markers (`*X`, `*Y`, `*XY`) for volume/growth spikes
- Deterministic seeding via `PRIORITYX_GLMM_SEED` for reproducible GLMM fits
- `plot_entity_trajectories()` for movement path visualization
- Transition driver analysis (experimental)

---

## v0.1.0 (2024-10)

**Initial Release**

- Core GLMM estimation with Poisson mixed effects (statsmodels backend)
- `fit_priority_matrix()` main API for entity prioritization
- Quadrant classification (Q1-Q4) based on volume and growth
- Priority matrix scatter plot visualization
- Quarterly, yearly, and semiannual temporal granularity
- Date filtering and minimum observation thresholds
- CSV and plot export with configurable output directories
