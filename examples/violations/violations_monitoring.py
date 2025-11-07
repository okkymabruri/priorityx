# %%
# compliance violations monitoring example
import os
import pandas as pd
from datetime import datetime, timedelta
import random

from priorityx.core.glmm import fit_priority_matrix
from priorityx.viz.matrix import plot_priority_matrix

random.seed(44)

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
]
# %%
# generate violations over 2 years
data = []
base_date = datetime(2023, 1, 1)

for dept_idx, dept in enumerate(departments):
    base_rate = 2 + dept_idx
    growth_rate = (dept_idx - 4.5) / 20

    for quarter in range(8):
        quarter_date = base_date + timedelta(days=quarter * 91)
        n_violations = int(base_rate + quarter * growth_rate + random.gauss(0, 1))
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
# %%
results, stats = fit_priority_matrix(
    df,
    entity_col="department",
    timestamp_col="date",
    temporal_granularity="quarterly",
    min_observations=6,
)
# %%
print("Compliance Violations Priority Matrix:")
print(results[["entity", "Random_Intercept", "Random_Slope", "count", "quadrant"]])

plot_priority_matrix(
    results,
    entity_name="Department",
    show_quadrant_labels=True,
    save_plot=True,
    output_dir="examples/violations/plot",
)

# save results
os.makedirs("examples/violations/results", exist_ok=True)
results.to_csv("examples/violations/results/priority_matrix.csv", index=False)
print()
print("Outputs saved to examples/violations/plot/ and examples/violations/results/")

# %%
