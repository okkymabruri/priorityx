# %%
# it incident monitoring example
from pathlib import Path

import pandas as pd

import priorityx as px
from priorityx.utils.helpers import (
    display_quadrant_summary,
    display_transition_summary,
)

BASE_DIR = Path(__file__).resolve().parent

# output directories (keep outputs inside examples/incidents/results)
PLOT_DIR = BASE_DIR / "results" / "plot"
CSV_DIR = BASE_DIR / "results" / "csv"

PLOT_DIR.mkdir(parents=True, exist_ok=True)
CSV_DIR.mkdir(parents=True, exist_ok=True)

DATA_PATH = BASE_DIR / "incidents.csv"

# upstream dataset (raw GitHub)
DATA_URL = (
    "https://raw.githubusercontent.com/okkymabruri/priorityx/main/"
    "examples/incidents/incidents.csv"
)

# load data
df = pd.read_csv(DATA_URL, parse_dates=["opened_at", "closed_at"])
print(f"Loaded incidents from: {DATA_URL}")

print(f"Loaded {len(df)} incidents for {df['service'].nunique()} services")
print(f"Date range: {df['opened_at'].min()} to {df['opened_at'].max()}")

# fit priority matrix
print()
print("PRIORITY MATRIX ANALYSIS")

temporal_granularity = "quarterly"
entity_name = "Service"
results = px.fit_priority_matrix(
    df,
    entity_col="service",
    timestamp_col="opened_at",
    temporal_granularity=temporal_granularity,
    min_observations=8,
    min_total_count=20,
)

print(f"\nAnalyzed {len(results)} services")
print(results[["entity", "x_score", "y_score", "count", "quadrant"]])

display_quadrant_summary(results, entity_name=entity_name, min_count=0)

# visualize with simplified path API
px.plot_priority_matrix(
    results,
    entity_name=entity_name,
    show_quadrant_labels=True,
    plot_path=PLOT_DIR / "priority_matrix-service-Q.png",
    csv_path=CSV_DIR / "priority_matrix-service-Q.csv",
)

# track movement
print()
print("CUMULATIVE MOVEMENT TRACKING")

movement, meta = px.track_movement(
    df,
    entity_col="service",
    timestamp_col="opened_at",
    quarters=["2023-01-01", "2026-01-01"],
    min_total_count=20,
    temporal_granularity=temporal_granularity,
    return_metadata=True,
)

print(
    f"\nTracked {meta['entities_tracked']} services over {meta['quarters_analyzed']} quarters"
)

# save movement
movement.to_csv(CSV_DIR / "trajectories-service-Q.csv", index=False)
print(f"Movement CSV saved: {CSV_DIR / 'trajectories-service-Q.csv'}")

# visualize entity trajectories with simplified path API
px.plot_entity_trajectories(
    movement,
    entity_name=entity_name,
    max_entities=5,
    plot_path=PLOT_DIR / "trajectories-service-Q.png",
    csv_path=CSV_DIR / "trajectories-service-Q.csv",
)

# detect transitions
transitions = px.extract_transitions(movement, focus_risk_increasing=True)

print(f"\nDetected {len(transitions)} risk-increasing transitions")
display_transition_summary(transitions, entity_name=entity_name)

px.plot_transition_timeline(
    transitions,
    entity_name=entity_name,
    movement_df=movement,
    plot_path=PLOT_DIR / "transitions-service-Q.png",
    csv_path=CSV_DIR / "transitions-service-Q.csv",
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
        driver_analysis = px.extract_transition_drivers(
            movement_df=movement,
            df_raw=df,
            entity_name=trans["entity"],
            quarter_from=prev_quarter,
            quarter_to=trans["transition_quarter"],
            entity_col="service",
            timestamp_col="opened_at",
            top_n_subcategories=5,
            min_subcategory_delta=2,
        )

        px.display_transition_drivers(driver_analysis)

print()
print(f"Analysis complete. Check {PLOT_DIR}/ and {CSV_DIR}/")

# %%
