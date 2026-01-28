# %%
import random
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd

import priorityx as px
from priorityx.utils.helpers import (
    display_quadrant_summary,
    display_transition_summary,
)

random.seed(42)

# output directories
PLOT_DIR = Path("plot")
CSV_DIR = Path("results")

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

results = px.fit_priority_matrix(
    df,
    entity_col="department",
    timestamp_col="date",
    temporal_granularity=temporal_granularity,
    min_observations=6,
)
print("Compliance Violations Priority Matrix:")
print(results[["entity", "x_score", "y_score", "count", "quadrant"]])

display_quadrant_summary(results, entity_name=entity_name, min_count=0)

# visualize with simplified path API
px.plot_priority_matrix(
    results,
    entity_name=entity_name,
    show_quadrant_labels=True,
    plot_path=PLOT_DIR / "priority_matrix-department-Q.png",
    csv_path=CSV_DIR / "priority_matrix-department-Q.csv",
)

movement, meta = px.track_movement(
    df,
    entity_col="department",
    timestamp_col="date",
    quarters=["2023-01-01", "2025-01-01"],
    min_total_count=5,
    temporal_granularity=temporal_granularity,
    return_metadata=True,
)

# save movement
movement.to_csv(CSV_DIR / "trajectories-department-Q.csv", index=False)
print(f"Movement CSV saved: {CSV_DIR / 'trajectories-department-Q.csv'}")

transitions = px.extract_transitions(movement, focus_risk_increasing=True)

print(f"\nDetected {len(transitions)} risk-increasing transitions")
display_transition_summary(transitions, entity_name=entity_name)

# visualize with simplified path API
px.plot_transition_timeline(
    transitions,
    entity_name=entity_name,
    movement_df=movement,
    plot_path=PLOT_DIR / "transitions-department-Q.png",
    csv_path=CSV_DIR / "transitions-department-Q.csv",
)

print()
print(f"Outputs saved to {PLOT_DIR}/ and {CSV_DIR}/")

# %%
