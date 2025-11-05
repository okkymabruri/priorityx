# Priorityx

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
import polars as pl
from priorityx.core.glmm import fit_priority_matrix
from priorityx.viz.matrix import plot_priority_matrix

df = pl.read_csv("data.csv")

results, stats = fit_priority_matrix(
    df,
    entity_col="service",
    timestamp_col="date",
    temporal_granularity="quarterly"
)

plot_priority_matrix(results, entity_name="Service", save_plot=True)
```

## Features

- GLMM-based priority classification (Q1-Q4 quadrants)
- Transition detection over time
- Movement tracking
- Visualization

## Use Cases

IT incidents, software bugs, compliance violations, performance monitoring.

## Documentation

- [Quick Start](docs/quickstart.md)
- [API Reference](docs/api-reference.md)
- [Methodology](docs/methodology.md)