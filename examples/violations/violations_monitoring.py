import os
import random
from datetime import datetime, timedelta

import pandas as pd

from priorityx.core.glmm import fit_priority_matrix
from priorityx.tracking.movement import track_cumulative_movement
from priorityx.tracking.transitions import extract_transitions
from priorityx.viz.matrix import plot_priority_matrix
from priorityx.viz.timeline import plot_transition_timeline
from priorityx.utils.helpers import (
    display_quadrant_summary,
    display_transition_summary,
)

random.seed(42)

# departments
departments = [
    "Finance",
    "HR",
    "IT",
    "Sales",
    "Marketing",
    "Operations",
    "Legal",
    "Procurement",
    "Customer Service",
    "R&D",
    "Compliance",
    "Facilities",
    "Product",
]
print()
print("COMPLIANCE VIOLATIONS MONITORING")

# generate violations over 2 years
data = []
base_date = datetime(2023, 1, 1)

for dept_idx, dept in enumerate(departments):
    base_rate = 2 + dept_idx
    growth_rate = (dept_idx - 4.5) / 20

    for quarter in range(8):
        quarter_date = base_date + timedelta(days=quarter * 91)
        n_violations = int(base_rate + quarter * growth_rate + random.gauss(0, 1.5))
        n_violations = max(1, n_violations)

        for _ in range(n_violations):
            days_offset = random.randint(0, 90)
            violation_date = quarter_date + timedelta(days=days_offset)

            data.append(
                {
                    "department": dept,
                    "date": violation_date,
                }
            )

df = pd.DataFrame(data)
temporal_granularity = "quarterly"
entity_name = "Department"

PLOT_DIR = "examples/violations/plot"
RESULTS_DIR = "examples/violations/results"
os.makedirs(PLOT_DIR, exist_ok=True)
os.makedirs(RESULTS_DIR, exist_ok=True)

results, stats = fit_priority_matrix(
    df,
    entity_col="department",
    timestamp_col="date",
    temporal_granularity=temporal_granularity,
    min_observations=6,
)
print("Compliance Violations Priority Matrix:")
print(results[["entity", "Random_Intercept", "Random_Slope", "count", "quadrant"]])

display_quadrant_summary(results, entity_name=entity_name, min_count=0)

plot_priority_matrix(
    results,
    entity_name=entity_name,
    show_quadrant_labels=True,
    save_plot=True,
    save_csv=True,
    output_dir=PLOT_DIR,
)

movement, meta = track_cumulative_movement(
    df,
    entity_col="department",
    timestamp_col="date",
    quarters=["2023-01-01", "2025-01-01"],
    min_total_count=5,
    temporal_granularity=temporal_granularity,
)

timestamp = datetime.now().strftime("%Y%m%d")
granularity_suffix = {
    "quarterly": "Q",
    "yearly": "Y",
    "semiannual": "S",
}.get(temporal_granularity, "Q")
movement_path = (
    f"{RESULTS_DIR}/trajectories-{entity_name.lower()}-"
    f"{granularity_suffix}-{timestamp}.csv"
)
movement.to_csv(movement_path, index=False)
print(f"Movement CSV saved: {movement_path}")
transitions = extract_transitions(movement, focus_risk_increasing=True)

print(f"\nDetected {len(transitions)} risk-increasing transitions")
display_transition_summary(transitions, entity_name=entity_name)

plot_transition_timeline(
    transitions,
    entity_name=entity_name,
    save_plot=True,
    save_csv=True,
    output_dir=PLOT_DIR,
    movement_df=movement,
)

print()
print("Outputs saved to examples/violations/plot/ and examples/violations/results/")
