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

### Deterministic runs

Set `PRIORITYX_GLMM_SEED` (or call `set_glmm_random_seed()`) before running analyses to obtain repeatable GLMM estimates during debugging or CI checks:

```bash
PRIORITYX_GLMM_SEED=1234 python tmp/complaints_analysis.py
```

```python
import pandas as pd
from priorityx.core.glmm import fit_priority_matrix
from priorityx.viz.matrix import plot_priority_matrix

df = pd.read_csv("data.csv")

results, stats = fit_priority_matrix(
    df,
    entity_col="service",
    timestamp_col="date",
    temporal_granularity="quarterly"
)

plot_priority_matrix(results, entity_name="Service", save_plot=True)
```

## Features

- GLMM-based priority matrix (Q1–Q4) with entity-level intercept/slope insights
- Priority-based transition timeline (Crisis / Investigate / Monitor / Low) with spike markers (`*X`, `*Y`, `*XY`)
- Cumulative movement tracking and trajectory visualizations
- Deterministic seeding option for reproducible GLMM runs (set `PRIORITYX_GLMM_SEED`)

## Use Cases

IT incidents, software bugs, compliance violations, performance monitoring.

## Documentation

- [Quick Start](docs/quickstart.md)
- [API Reference](docs/api-reference.md)
- [Methodology](docs/methodology.md)
- [Priority Classification](docs/priority_classification.md)