# Priorityx: Entity prioritization and escalation detection using GLMM statistical models

[![PyPI version](https://badge.fury.io/py/priorityx.svg)](https://badge.fury.io/py/priorityx)
[![Downloads](https://static.pepy.tech/badge/priorityx)](https://pepy.tech/project/priorityx)
[![Tests](https://github.com/okkymabruri/priorityx/workflows/Tests/badge.svg)](https://github.com/okkymabruri/priorityx/actions)
[![Python](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

Entity prioritization and escalation detection using GLMM statistical models

## Installation

```bash
pip install priorityx
```

## Quick Start

```python
import pandas as pd
import priorityx as px

df = pd.read_csv("data.csv")

# Default: volume x growth (single GLMM)
results, stats = px.fit_priority_matrix(
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
results, _ = px.fit_priority_matrix(
    df,
    entity_col="service",
    timestamp_col="date",
    y_metric="resolution_days",
)

# Custom both axes: disputed_amount × paid_amount
results, _ = px.fit_priority_matrix(
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

- GLMM-based priority matrix (Q1–Q4) with entity-level intercept/slope insights
- Priority-based transition timeline (Crisis / Investigate / Monitor / Low) with spike markers (`*X`, `*Y`, `*XY`)
- Cumulative movement tracking and trajectory visualizations
- Transition driver analysis that surfaces top subcategories causing quadrant shifts with spike summaries
- Deterministic seeding option for reproducible GLMM runs (set `PRIORITYX_GLMM_SEED`)

## Use Cases

IT incidents, software bugs, compliance violations, performance monitoring.

## Documentation

- [Quick Start](docs/quickstart.md)
- [API Reference](docs/api-reference.md)
- [Methodology](docs/methodology.md)
- [Priority Classification](docs/priority_classification.md)