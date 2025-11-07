# %%
# software bug tracking example
import os
import pandas as pd
from priorityx.core.glmm import fit_priority_matrix
from priorityx.viz.matrix import plot_priority_matrix

# %%
# load bug reports
df = pd.read_csv("examples/bugs/bugs.csv")

# parse date column
df["date"] = pd.to_datetime(df["reported_date"])

# %%
# fit priority matrix
results, stats = fit_priority_matrix(
    df,
    entity_col="component",
    timestamp_col="date",
    temporal_granularity="quarterly",
    min_observations=4,
)

# %%
# display results
print("Software Bug Priority Matrix:")
print(results[["entity", "Random_Intercept", "Random_Slope", "count", "quadrant"]])

# %%
# visualize
plot_priority_matrix(
    results,
    entity_name="Component",
    show_quadrant_labels=True,
    save_plot=True,
    output_dir="examples/bugs/plot",
)

# save results
os.makedirs("examples/bugs/results", exist_ok=True)
results.to_csv("examples/bugs/results/priority_matrix.csv", index=False)
print()
print("Outputs saved to examples/bugs/plot/ and examples/bugs/results/")

# %%
