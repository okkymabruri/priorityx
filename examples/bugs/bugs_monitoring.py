# %%
# software bug tracking example
import polars as pl
from priorityx.core.glmm import fit_priority_matrix
from priorityx.viz.matrix import plot_priority_matrix

# %%
# load bug reports
df = pl.read_csv("examples/bugs/bugs.csv")

# parse date column
df = df.with_columns(
    pl.col("reported_date").str.to_datetime().cast(pl.Date).alias("date")
)

# %%
# fit priority matrix
results, stats = fit_priority_matrix(
    df,
    entity_col="component",
    timestamp_col="date",
    temporal_granularity="quarterly",
    min_observations=4
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
    output_dir="examples/bugs/output"
)
print("\nPlot saved to examples/bugs/output/")

# %%
