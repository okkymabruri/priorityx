# %%
import random
from datetime import datetime, timedelta

import pandas as pd

import priorityx as px
from priorityx.utils.helpers import (
    display_quadrant_summary,
    display_transition_summary,
    save_dataframe_to_csv,
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

results, stats = px.fit_priority_matrix(
    df,
    entity_col="department",
    timestamp_col="date",
    temporal_granularity=temporal_granularity,
    min_observations=6,
)
print("Compliance Violations Priority Matrix:")
print(results[["entity", "Random_Intercept", "Random_Slope", "count", "quadrant"]])

display_quadrant_summary(results, entity_name=entity_name, min_count=0)

px.plot_priority_matrix(
    results,
    entity_name=entity_name,
    show_quadrant_labels=True,
    save_plot=True,
    save_csv=True,
)

movement, meta = px.track_cumulative_movement(
    df,
    entity_col="department",
    timestamp_col="date",
    quarters=["2023-01-01", "2025-01-01"],
    min_total_count=5,
    temporal_granularity=temporal_granularity,
)

movement_path = save_dataframe_to_csv(
    movement,
    artifact="trajectories",
    entity_name=entity_name,
    temporal_granularity=temporal_granularity,
)
print(f"Movement CSV saved: {movement_path}")
transitions = px.extract_transitions(movement, focus_risk_increasing=True)

print(f"\nDetected {len(transitions)} risk-increasing transitions")
display_transition_summary(transitions, entity_name=entity_name)

px.plot_transition_timeline(
    transitions,
    entity_name=entity_name,
    save_plot=True,
    save_csv=True,
    movement_df=movement,
)

print()
print("Outputs saved to plot/ and results/ in the current working directory.")

# %%
