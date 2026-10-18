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

**IT Incidents** — generate a local CSV, then run monitoring
```bash
python examples/incidents/generate_incidents.py
python examples/incidents/incident_monitoring.py
```

**Compliance Violations** (495 violations, 10 departments) — synthetic dataset
```bash
python examples/violations/violations_monitoring.py
```

**Software Bugs** (576 bugs, 10 components) — pulls CSV from GitHub raw

## Output

The incidents example writes results to:

- `examples/incidents/results/plot/` - Visualizations (PNG files)
- `examples/incidents/results/csv/` - Data tables (CSV files)
