# it incident monitoring example

import pandas as pd

from priorityx.core.glmm import fit_priority_matrix
from priorityx.tracking.movement import track_cumulative_movement
from priorityx.tracking.transitions import extract_transitions
from priorityx.tracking.drivers import (
    extract_transition_drivers,
    display_transition_drivers,
)
from priorityx.viz.matrix import plot_priority_matrix
from priorityx.viz.timeline import plot_transition_timeline
from priorityx.viz.trajectory import plot_entity_trajectories
from priorityx.utils.helpers import (
    display_quadrant_summary,
    display_transition_summary,
    save_dataframe_to_csv,
)

# load data
df = pd.read_csv("examples/incidents/incidents.csv")
df["date"] = pd.to_datetime(df["date"])

print(f"Loaded {len(df)} incidents for {df['service'].nunique()} services")
print(f"Date range: {df['date'].min()} to {df['date'].max()}")

# fit priority matrix
print()
print("PRIORITY MATRIX ANALYSIS")

temporal_granularity = "quarterly"
entity_name = "Service"
results, stats = fit_priority_matrix(
    df,
    entity_col="service",
    timestamp_col="date",
    temporal_granularity=temporal_granularity,
    min_observations=8,
    min_total_count=20,
)

print(f"\nAnalyzed {len(results)} services")
print(results[["entity", "Random_Intercept", "Random_Slope", "count", "quadrant"]])

display_quadrant_summary(results, entity_name=entity_name, min_count=0)

# visualize
plot_priority_matrix(
    results,
    entity_name=entity_name,
    show_quadrant_labels=True,
    save_plot=True,
    save_csv=True,
    output_dir="examples/incidents/plot",
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
    temporal_granularity=temporal_granularity,
)

print(
    f"\nTracked {meta['entities_tracked']} services over {meta['quarters_analyzed']} quarters"
)

# save movement
movement_path = save_dataframe_to_csv(
    movement,
    artifact="trajectories",
    entity_name=entity_name,
    temporal_granularity=temporal_granularity,
    output_dir="examples/incidents/results",
)
print(f"Movement CSV saved: {movement_path}")

# visualize entity trajectories
plot_entity_trajectories(
    movement,
    entity_name=entity_name,
    max_entities=5,
    save_plot=True,
    save_csv=True,
    output_dir="examples/incidents/plot",
    results_dir="examples/incidents/results",
)

# detect transitions
transitions = extract_transitions(movement, focus_risk_increasing=True)

print(f"\nDetected {len(transitions)} risk-increasing transitions")
display_transition_summary(transitions, entity_name=entity_name)

plot_transition_timeline(
    transitions,
    entity_name=entity_name,
    save_plot=True,
    save_csv=True,
    output_dir="examples/incidents/plot",
    movement_df=movement,
)

critical_transitions = transitions[transitions["risk_level"] == "critical"]
if len(critical_transitions) > 0:
    trans = critical_transitions.iloc[0]

    print()
    print("DRIVER ANALYSIS EXAMPLE")
    print(f"Analyzing: {trans['entity']}")
    print(f"Transition: {trans['from_quadrant']} -> {trans['to_quadrant']}")
    print(f"Quarter: {trans['transition_quarter']}")

    entity_movement = (
        movement[movement["entity"] == trans["entity"]]
        .sort_values("quarter")
        .reset_index(drop=True)
    )
    trans_idx = entity_movement[
        entity_movement["quarter"] == trans["transition_quarter"]
    ].index[0]
    prev_quarter = (
        entity_movement.loc[trans_idx - 1, "quarter"] if trans_idx > 0 else None
    )

    if prev_quarter:
        driver_analysis = extract_transition_drivers(
            movement_df=movement,
            df_raw=df,
            entity_name=trans["entity"],
            quarter_from=prev_quarter,
            quarter_to=trans["transition_quarter"],
            entity_col="service",
            timestamp_col="date",
        )

        display_transition_drivers(driver_analysis)

print()
print(
    "Analysis complete. Check examples/incidents/plot/ and examples/incidents/results/"
)

# %%
