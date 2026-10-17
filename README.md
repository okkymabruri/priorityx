# Priorityx: Entity prioritization and escalation detection using GLMM statistical models

[![PyPI version](https://badge.fury.io/py/priorityx.svg)](https://badge.fury.io/py/priorityx)
[![Downloads](https://static.pepy.tech/badge/priorityx)](https://pepy.tech/project/priorityx)
[![Tests](https://github.com/okkymabruri/priorityx/workflows/Tests/badge.svg)](https://github.com/okkymabruri/priorityx/actions)
[![Python](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

Entity prioritization and escalation detection using GLMM statistical models

## Installation

The v0.7.0 development branch requires Python 3.12 or later. This checkout uses
Python 3.12 by default for development; published v0.6.3 keeps its original Python
requirement.

```bash
pip install priorityx
```

## AutoViz: interactive saved-results workspace

Explore a linked **quadrant matrix → YTD transition timeline → trajectories**
and regenerate layouts through browser controls. AutoViz reads saved results;
opening charts or changing their layout does not fit models.

AutoViz is part of the **unreleased v0.7.0 development branch**, not the published
v0.6.3 package. In a Python 3.12+ virtual environment, run these commands from
this checkout (`feature/v0.7.0-autoviz`):

```bash
python -m pip install -e .
python -m priorityx app
```

The app opens in your browser on a free `127.0.0.1` port. It works locally on
macOS, Windows and Linux without Node or a hosted server. Keep the terminal
running while using the app; press Ctrl+C to stop it.

1. **Open results**: choose a saved result bundle, or **Import CSV files** and
   assign your saved matrix, movement and transition CSVs. Supply the type label,
   cadence, coverage and source metadata. These are PriorityX result tables;
   source-specific raw data must be transformed by your own adapter first.
2. **Choose Type and cadence**: labels come from your results. Quarterly opens
   when available. The timeline shows YTD through the latest saved period;
   full history is retained for event classification and trajectories.
3. **Inspect and adjust**: select an entity to link the charts, zoom or **Reset
   view**, and open **View data** for exact values. Use **Layout** to adjust equal
   panel sizes and apply the changes. **Save settings** and **Load settings**
   inside Layout preserve a portable view configuration.
4. **Export**: **Export → Save offline HTML** saves an interactive view that
   reopens without Python or a network connection. Matrix SVG also works offline;
   print PNG/SVG exports require the running local app. The HTML contains the
   full saved data, so share it with the same care as the source results.

To open a bundle directly:

```bash
python -m priorityx app --bundle results.json
```

<details>
<summary>Create a bundle from existing saved CSVs</summary>

```python
from priorityx.results import ResultBundle, import_results_csv

dataset = import_results_csv(
    entity_type="work_unit", type_label="Work units",
    cadence="quarterly", source_id="saved-analysis",
    coverage_start="2025-Q1", as_of="2025-Q4",
    matrix_path="priority_matrix.csv",
    movement_path="movement.csv",
    transitions_path="transitions.csv",
)
ResultBundle([dataset]).save("results.json")
```

Use your actual file paths and coverage dates. Quarterly dates use `YYYY-Qn`;
monthly dates use `YYYY-MM` with `cadence="monthly"`. A bundle can hold multiple
types and cadences by including more datasets in `ResultBundle([...])`.

</details>

See the [workspace guide](docs/app.md) for controls, layout, state and exports,
and the [saved-result contract](docs/saved-results.md) for import validation and
trajectory selection.

## Quick Start

```python
import pandas as pd
import priorityx as px

df = pd.read_csv("data.csv")

# Default: volume x growth (single GLMM)
results = px.fit_priority_matrix(
    df,
    entity_col="service",
    timestamp_col="date",
    temporal_granularity="quarterly",
)
# Returns: entity, x_score, y_score, count, quadrant

px.plot_priority_matrix(results, entity_name="Service", save_plot=True)
```

### Custom Axes

```python
# Custom Y axis: volume × resolution_days (two GLMMs)
results = px.fit_priority_matrix(
    df,
    entity_col="service",
    timestamp_col="date",
    y_metric="resolution_days",
)

# Custom both axes: disputed_amount × paid_amount
results = px.fit_priority_matrix(
    df,
    entity_col="service",
    timestamp_col="date",
    x_metric="disputed_amount",
    y_metric="paid_amount",
)
```

### Composite Indices

```python
# Add entity metrics
metrics = px.aggregate_entity_metrics(
    df,
    entity_col="service",
    duration_start_col="opened_at",
    duration_end_col="closed_at",
    primary_col="exposure",
    secondary_col="recovery",
)
results = results.merge(metrics, left_on="entity", right_on="service", how="left")

# Add weighted indices: RI (Risk), SQI (Service Quality), EWI (Early Warning)
results = px.add_priority_indices(
    results,
    volume_col="count",
    growth_col="y_score",
    severity_col="total_primary",
    resolution_col="mean_duration",
    recovery_col="secondary_to_primary_ratio",
    # customize weights (default shown)
    w_volume=0.4, w_growth=0.4, w_severity=0.2,
    w_resolution=0.5, w_recovery=0.5,
    w_risk=0.7, w_quality=0.3,
)

# Top priority entities
top_risks = results.nlargest(10, "EWI")
```

## Features

- AutoViz local workspace with linked interactive charts, automatic layout and offline HTML export (v0.7.0 development)
- GLMM-based priority matrix (Q1–Q4) with entity-level intercept/slope insights
- Priority-based transition timeline (Crisis / Investigate / Monitor / Low) with spike markers (`*X`, `*Y`, `*XY`)
- Cumulative movement tracking and trajectory visualizations
- Transition driver analysis that surfaces top subcategories causing quadrant shifts with spike summaries
- Deterministic seeding option for reproducible GLMM runs (set `PRIORITYX_GLMM_SEED`)

## Use Cases

IT incidents, software bugs, compliance violations, performance monitoring.

## Documentation

- [AutoViz Workspace](docs/app.md)
- [Saved Results and CSV Import](docs/saved-results.md)
- [Quick Start](docs/quickstart.md)
- [API Reference](docs/api-reference.md)
- [Methodology](docs/methodology.md)
- [Priority Classification](docs/priority_classification.md)
