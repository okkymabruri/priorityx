# IT incident monitoring example
import polars as pl
from priorityx.core.glmm import fit_priority_matrix
from priorityx.tracking.movement import track_cumulative_movement
from priorityx.tracking.transitions import extract_transitions
from priorityx.tracking.drivers import extract_transition_drivers, display_transition_drivers
from priorityx.viz.matrix import plot_priority_matrix
from priorityx.viz.timeline import plot_transition_timeline
from priorityx.utils.helpers import display_quadrant_summary, display_transition_summary

# load data
df = pl.read_csv("examples/incidents/incidents.csv")
df = df.with_columns(pl.col("date").str.to_datetime().cast(pl.Date))

print(f"Loaded {len(df)} incidents for {df['service'].n_unique()} services")
print(f"Date range: {df['date'].min()} to {df['date'].max()}")

# fit priority matrix
print()
print("PRIORITY MATRIX ANALYSIS")

results, stats = fit_priority_matrix(
    df,
    entity_col="service",
    timestamp_col="date",
    temporal_granularity="quarterly",
    min_observations=8,
    min_total_count=20
)

print(f"\nAnalyzed {len(results)} services")
print(results[["entity", "Random_Intercept", "Random_Slope", "count", "quadrant"]])

display_quadrant_summary(results, entity_name="Service", min_count=0)

# visualize
plot_priority_matrix(
    results,
    entity_name="Service",
    show_quadrant_labels=False,
    save_plot=True,
    output_dir="examples/incidents/output"
)

# track movement
print()
print("CUMULATIVE MOVEMENT TRACKING")

movement, meta = track_cumulative_movement(
    df,
    entity_col="service",
    timestamp_col="date",
    quarters=["2022-01-01", "2025-01-01"],
    min_total_count=20,
    temporal_granularity="quarterly"
)

print(f"\nTracked {meta['entities_tracked']} services over {meta['quarters_analyzed']} quarters")

# detect transitions
transitions = extract_transitions(movement, focus_risk_increasing=True)

if not transitions.empty:
    print(f"\nDetected {len(transitions)} risk-increasing transitions")
    display_transition_summary(transitions, entity_name="Service")

    # visualize transitions
    plot_transition_timeline(
        transitions,
        entity_name="Service",
        save_plot=True,
        output_dir="examples/incidents/output"
    )

    # analyze drivers for first transition (example)
    if len(transitions) > 0:
        first_transition = transitions.iloc[0]

        print()
        print("DRIVER ANALYSIS EXAMPLE")
        print(f"Analyzing: {first_transition['entity']}")
        print(f"Transition: {first_transition['from_quadrant']} -> {first_transition['to_quadrant']}")
        print(f"Period: {first_transition['from_quarter']} -> {first_transition['transition_quarter']}")

        # extract drivers
        driver_analysis = extract_transition_drivers(
            movement_df=movement,
            df_raw=df,
            entity_name=first_transition["entity"],
            quarter_from=first_transition["from_quarter"],
            quarter_to=first_transition["transition_quarter"],
            entity_col="service",
            timestamp_col="date"
        )

        display_transition_drivers(driver_analysis)

print("\nAnalysis complete. Check examples/incidents/output/ for plots.")
