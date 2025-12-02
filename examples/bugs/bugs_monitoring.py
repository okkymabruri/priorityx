# %%
# software bug tracking example (data pulled from GitHub raw)
import pandas as pd

import priorityx as px

RAW_DATA_URL = "https://raw.githubusercontent.com/okkymabruri/priorityx/main/examples/bugs/bugs.csv"

# load bug reports from GitHub raw
df = pd.read_csv(RAW_DATA_URL, parse_dates=["reported_date"])
df["date"] = df["reported_date"]

# fit priority matrix
temporal_granularity = "quarterly"
entity_name = "Component"

results, stats = px.fit_priority_matrix(
    df,
    entity_col="component",
    timestamp_col="date",
    temporal_granularity=temporal_granularity,
    min_observations=4,
)

# display results
print("Software Bug Priority Matrix:")
print(results[["entity", "Random_Intercept", "Random_Slope", "count", "quadrant"]])

# visualize
px.plot_priority_matrix(
    results,
    entity_name=entity_name,
    show_quadrant_labels=True,
    save_plot=True,
    save_csv=True,
)
print()
print("Outputs saved to plot/ and results/ (under the current working directory)")

# %%
