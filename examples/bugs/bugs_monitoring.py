# %%
# software bug tracking example (data pulled from GitHub raw)
from pathlib import Path

import pandas as pd

import priorityx as px

RAW_DATA_URL = "https://raw.githubusercontent.com/okkymabruri/priorityx/main/examples/bugs/bugs.csv"

# output directories
PLOT_DIR = Path("plot")
CSV_DIR = Path("results")

# load bug reports from GitHub raw
df = pd.read_csv(RAW_DATA_URL, parse_dates=["reported_date"])
df["date"] = df["reported_date"]

# fit priority matrix
temporal_granularity = "quarterly"
entity_name = "Component"

results = px.fit_priority_matrix(
    df,
    entity_col="component",
    timestamp_col="date",
    temporal_granularity=temporal_granularity,
    min_observations=4,
)

# display results
print("Software Bug Priority Matrix:")
print(results[["entity", "x_score", "y_score", "count", "quadrant"]])

# visualize with simplified path API
px.plot_priority_matrix(
    results,
    entity_name=entity_name,
    show_quadrant_labels=True,
    plot_path=PLOT_DIR / "priority_matrix-component-Q.png",
    csv_path=CSV_DIR / "priority_matrix-component-Q.csv",
)
print()
print(f"Outputs saved to {PLOT_DIR}/ and {CSV_DIR}/")

# %%
