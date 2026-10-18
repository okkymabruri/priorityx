# Examples

These examples demonstrate priorityx usage with different datasets.

## Explore saved results in AutoViz

Open the [IT incidents sample](autoviz/incidents-quarterly.json) without fitting models:

```sh
python -m priorityx app --bundle examples/autoviz/incidents-quarterly.json
```

Run this from the repository root after [installation](../docs/installation.md).
The [walkthrough](../docs/autoviz-example.md) explains the linked charts and
the five-service saved-result sample's provenance.

## Prerequisites

Follow the [installation guide](../docs/installation.md) for package or source setup.

## Running Examples

**IT Incidents** — downloads the existing CSV from GitHub, fits models and writes results
```bash
python examples/incidents/incident_monitoring.py
```

**Compliance Violations** — generates demonstration events in memory and fits models
```bash
python examples/violations/violations_monitoring.py
```

**Software Bugs** — downloads the existing CSV from GitHub and fits a matrix

```sh
python examples/bugs/bugs_monitoring.py
```

Run analysis scripts from the repository root. They perform fitting and can
replace their named output files; the saved AutoViz example above only opens
existing results. The optional `incidents/generate_incidents.py` generator writes
a new local CSV, but `incident_monitoring.py` currently reads the GitHub URL
rather than that local file.

## Output

The incidents example writes results to:

- `examples/incidents/results/plot/` - Visualizations (PNG files)
- `examples/incidents/results/csv/` - Data tables (CSV files)

The bugs and violations scripts use `plot/` and `results/` in the current working
directory. In the incidents script, plotting trajectories writes a selected
subset over `trajectories-service-Q.csv`; keep a separately named full movement
table if you need all entities for AutoViz. The ready-made bundle preserves all
available history for its five selected services.
