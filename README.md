# PriorityX

[![PyPI version](https://badge.fury.io/py/priorityx.svg)](https://pypi.org/project/priorityx/)
[![Downloads](https://static.pepy.tech/badge/priorityx)](https://pepy.tech/project/priorityx)
[![Tests](https://github.com/okkymabruri/priorityx/workflows/Tests/badge.svg)](https://github.com/okkymabruri/priorityx/actions)
[![Python](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

Prioritize entities and detect escalation using GLMM statistical models.
Analyze event data in Python, then explore saved results in AutoViz.
Example applications include IT incidents, software bugs and compliance monitoring.

**[Installation](https://github.com/okkymabruri/priorityx/blob/main/docs/installation.md)** ·
**[AutoViz guide](https://github.com/okkymabruri/priorityx/blob/main/docs/app.md)** ·
**[Python quickstart](https://github.com/okkymabruri/priorityx/blob/main/docs/quickstart.md)** ·
**[API reference](https://github.com/okkymabruri/priorityx/blob/main/docs/api-reference.md)**

## AutoViz

Explore a linked **quadrant matrix → YTD transition timeline → trajectories**
in your browser. Select an entity across charts, inspect exact values, adjust
chart space and save an interactive HTML view that reopens offline.

![AutoViz showing five IT services: a quadrant matrix, 2025 YTD events and three recent trajectories.](https://raw.githubusercontent.com/okkymabruri/priorityx/main/docs/assets/autoviz-incidents.webp)

### Try the IT incidents example

Save the [example bundle](https://raw.githubusercontent.com/okkymabruri/priorityx/main/examples/autoviz/incidents-quarterly.json)
as `incidents-quarterly.json`, then run:

```sh
python -m priorityx app --bundle incidents-quarterly.json
```

This sample uses existing saved results from PriorityX's IT incidents example:
five services with quarterly history from 2023 to 2025. It opens on **Quarterly**,
with a **2025 YTD** timeline and three automatically selected trajectories.
Opening results and changing layouts do not fit models.

See the [example walkthrough](https://github.com/okkymabruri/priorityx/blob/main/docs/autoviz-example.md) for what to inspect and
the sample's provenance. To open your own results, run `python -m priorityx app`
and choose **Open results**. The [saved-result guide](https://github.com/okkymabruri/priorityx/blob/main/docs/saved-results.md#required-columns)
lists the identity, period and score columns required for CSV import.

## Python API

Fit a priority matrix from your event data and save a chart:

```python
import pandas as pd
import priorityx as px

events = pd.read_csv("events.csv", parse_dates=["opened_at"])
matrix = px.fit_priority_matrix(
    events,
    entity_col="service",
    timestamp_col="opened_at",
    temporal_granularity="quarterly",
)
px.plot_priority_matrix(matrix, entity_name="Service", plot_path="matrix.png")
```

PriorityX also provides cumulative movement tracking, transition detection,
driver analysis, custom score axes and weighted composite indices. The
[Python quickstart](https://github.com/okkymabruri/priorityx/blob/main/docs/quickstart.md) covers the analysis workflow;
the [API reference](https://github.com/okkymabruri/priorityx/blob/main/docs/api-reference.md) documents parameters and outputs.

## Documentation

| Guide | What it covers |
|---|---|
| [Installation](https://github.com/okkymabruri/priorityx/blob/main/docs/installation.md) | Python requirements, macOS/Linux and Windows setup, upgrades |
| [AutoViz example](https://github.com/okkymabruri/priorityx/blob/main/docs/autoviz-example.md) | Open and explore the saved IT incidents sample |
| [AutoViz workspace](https://github.com/okkymabruri/priorityx/blob/main/docs/app.md) | Linked charts, selection, layout, settings and exports |
| [Saved results](https://github.com/okkymabruri/priorityx/blob/main/docs/saved-results.md) | Data sources, identity/date columns, CSV mapping and validation |
| [Python quickstart](https://github.com/okkymabruri/priorityx/blob/main/docs/quickstart.md) | Fit, track movement and detect transitions |
| [Methodology](https://github.com/okkymabruri/priorityx/blob/main/docs/methodology.md) | Statistical models and score interpretation |
| [Priority classification](https://github.com/okkymabruri/priorityx/blob/main/docs/priority_classification.md) | Quadrants and transition classes |
| [Examples](https://github.com/okkymabruri/priorityx/blob/main/examples/README.md) | IT incidents, software bugs and compliance workflows |
