# Examples

These examples demonstrate priorityx usage with different datasets.

## Prerequisites

Install priorityx from PyPI:
```bash
pip install priorityx
```

Or install latest from source:
```bash
pip install git+https://github.com/okkymabruri/priorityx.git
```

## Running Examples

**IT Incidents** (1,621 incidents, 10 services) — pulls CSV from GitHub raw
```bash
python examples/incidents/incident_monitoring.py
```

**Compliance Violations** (495 violations, 10 departments) — synthetic dataset
```bash
python examples/violations/violations_monitoring.py
```

**Software Bugs** (576 bugs, 10 components) — pulls CSV from GitHub raw

## Output

Results saved to:
- `plot/` - Visualizations (PNG files)
- `results/` - Data tables (CSV files)
