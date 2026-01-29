# Priority Classification Overview

A four-tier priority system ranks quadrant transitions by urgency using movement velocity, magnitude, and spike detection. Priorities are computed inside `plot_transition_timeline(..., movement_df=...)` and saved in transition CSVs.

## Priority Tiers

| Priority | Label & Color | Main Triggers | Recommended Action |
|----------|---------------|---------------|--------------------|
| **1 – Crisis** 🔴 | Explosion requiring immediate response | ΔX ≥ 0.40 or ΔY ≥ 0.40; volume jump ≥ 50 with ≥500% growth; both axes spiking (`*XY`) | Launch crisis playbook, staff war room, monitor daily |
| **2 – Investigate** 🟠 | Rapid escalation needing urgent review | `|ΔX|` > 0.15 or `|ΔY|` > 0.15; entry into Q1 with strong position; ≥100% growth with ≥5 new complaints | Trigger early warning, assign analysts, tighten monitoring cadence |
| **3 – Monitor** 🟡 | Borderline movement worth watching | Position within ±0.10 of quadrant boundary; gentle Q1 entry | Track trend, document findings, review quarterly |
| **4 – Low** 🟢 | Stable or improving | No conditions above met | Maintain routine oversight |

## Spike Indicators

| Marker | Meaning | Threshold |
|--------|---------|-----------|
| `*Y` | Growth spike | ΔY ≥ 0.40 |
| `*X` | Volume spike | ΔX ≥ 0.40 |
| `*XY` | Simultaneous spikes | ΔX ≥ 0.40 **and** ΔY ≥ 0.40 |

## Threshold Calibration

These thresholds are **empirical calibrations** derived from regulatory monitoring of financial complaints, not statistical cutoffs from a known distribution.

### Why These Values?

| Threshold | Value | Calibration Rationale |
|-----------|-------|----------------------|
| Crisis spike | ±0.40 | Flags ~top 1% of period-over-period movements in OJK complaints data (2021-2024) |
| Velocity trigger | ±0.15 | Captures sustained acceleration above median movement |
| Borderline band | ±0.10 | Buffer zone around quadrant boundaries |

### Important Caveats

1. **Scale depends on data**: GLMM random effects are on log-scale (Poisson) or original scale (Gaussian). The absolute values depend on your data's variance structure.

2. **Domain calibration recommended**: These thresholds were tuned for financial complaints. For other domains (IT incidents, bugs), validate with your historical data:
   ```python
   # check your data's movement distribution
   movements = movement_df.groupby('entity')[['x_delta', 'y_delta']].agg(['mean', 'std', 'max'])
   print(movements.describe())
   ```

3. **Not statistical cutoffs**: Unlike z-scores where 2σ = 95th percentile, these are operational thresholds. Adjust based on your false-positive tolerance.

### Threshold Reference

| Metric | Cut-off | Notes |
|--------|---------|-------|
| Crisis spike | ±0.40 | Empirical: flags extreme moves in calibration data |
| Velocity trigger | ±0.15 | Empirical: sustained acceleration |
| Growth shock | ≥100% **and** ≥5 complaints | Filters out noise from tiny bases |
| Explosion | ≥500% **and** ≥50 complaints | High-volume surges escalated to Crisis |
| Borderline band | ±0.10 | Buffer zone around quadrant boundaries |

## Usage Guidelines

1. **Always supply movement data**: `plot_transition_timeline(transitions, movement_df=movement)` is required for priority scoring; omitting it defaults to Priority 2.
2. **Filter by priority**: e.g. `transitions[transitions["priority"] == 1]` to summarize crises; risk_level is retained for backward compatibility only.
3. **Inspect spike markers**: `*X`, `*Y`, `*XY` signal urgent within-quadrant acceleration that may precede cross-quadrant jumps.
4. **Adjust tracking range deliberately**: longer histories surface more transitions; short windows emphasize recent moves.

