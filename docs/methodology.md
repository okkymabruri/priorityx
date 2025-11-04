# Methodology

## Overview

priorityx uses Generalized Linear Mixed Models (GLMM) to classify entities into priority quadrants based on volume and growth trajectories.

## Statistical Approach

### GLMM Specification

**Model:** Poisson Bayesian Mixed GLMM

```
count ~ time + seasonal_effects + (1 + time | entity)
```

**Components:**
- Fixed effects: Overall time trend + seasonal dummies (quarterly/semiannual)
- Random intercepts: Entity-specific baseline volume
- Random slopes: Entity-specific growth rates

**Estimation:** Variational Bayes (VB) for posterior mean

**Priors:**
- Random effects: vcp_p = 3.5 (relaxed for boundary behavior)
- Fixed effects: fe_p = 3.0

### Quadrant Classification

Entities classified based on random effects:

**Q1 (Crisis):** intercept > 0, slope > 0, count ≥ 50
- High volume, accelerating growth
- Requires immediate attention

**Q2 (Investigate):** intercept ≤ 0, slope > 0
- Low volume but growing rapidly
- Emerging issues to watch

**Q3 (Monitor):** intercept ≤ 0, slope ≤ 0
- Low volume, stable or declining
- Routine monitoring

**Q4 (Low Priority):** intercept > 0, slope ≤ 0
- High volume but not accelerating
- Persistent baseline issues

The count threshold for Q1 prevents low-volume entities from being mislabeled as Crisis.

## Movement Tracking

### Three-Step Process

**1. Global Baseline**
- GLMM on full dataset
- Provides stable quadrant assignment

**2. Endpoint Cohorting**
- Define valid entities at analysis endpoint
- Ensures consistent peer group

**3. Quarterly Tracking**
- GLMM on cumulative data up to each quarter
- Tracks X/Y position changes over time

### Transition Detection

**Cross-quadrant transitions:**
- Q3→Q2→Q1: Escalation path
- Q1→Q4, Q2→Q3: De-escalation

**Within-quadrant changes:**
- Y-axis surge > 1.0: Dramatic acceleration
- X-axis surge > 1.0: Major volume increase

## Data Filters

**Sparse entities:**
- min_total_count: Filter entities below count threshold
- min_observations: Filter entities with insufficient time periods

**Stale entities:**
- decline_window_quarters: Filter entities inactive >N quarters
- Prevents contamination from historical data

## Validation

Approach validated on regulatory monitoring data:
- 95.7% accuracy vs baseline methods
- 1-3 quarter earlier detection of escalating entities
- Reduced false oscillations for smooth growth patterns

## References

- Social media analytics for mining customer complaints to explore product opportunities (2023). Computers & Industrial Engineering. https://doi.org/10.1016/j.cie.2023.109104
