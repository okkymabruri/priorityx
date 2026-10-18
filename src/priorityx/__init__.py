"""priorityx: Entity prioritization and escalation detection using GLMM statistical models.

The :mod:`priorityx.api` module exposes a small convenience facade so
users can write::

    import priorityx as px
    results = px.fit_priority_matrix(df, entity_col="service", timestamp_col="date")
    results, stats = px.fit_priority_matrix(
        df, entity_col="service", timestamp_col="date", return_stats=True
    )

while more advanced workflows can continue to import from the
``core``, ``tracking`` and ``viz`` subpackages directly.

## current version API (consolidated)

Use ``fit_priority_matrix()`` for count-based or custom-metric score axes:

    # Default: volume x growth
    results = px.fit_priority_matrix(df, entity_col="service", timestamp_col="date")

    # Custom Y axis: volume x resolution_days
    results = px.fit_priority_matrix(
        df, entity_col="service", timestamp_col="date", y_metric="resolution_days"
    )

    # Custom both axes: disputed x paid
    results = px.fit_priority_matrix(
        df, entity_col="service", timestamp_col="date",
        x_metric="disputed", y_metric="paid", y_effect="intercept"
    )

Default return: a DataFrame with entity, x_score, y_score, count and quadrant.
Pass return_stats=True for a (DataFrame, statistics dict) tuple.
The fitting cadence defaults to yearly; set temporal_granularity explicitly
when quarterly or monthly analysis is intended.
"""

from .api import (  # noqa: F401
    aggregate_entity_metrics,
    add_priority_indices,
    display_transition_drivers,
    extract_transition_drivers,
    extract_transitions,
    fit_priority_matrix,
    load_or_track_movement,
    plot_entity_trajectories,
    plot_priority_matrix,
    plot_transition_timeline,
    layout_transition_labels,
    set_glmm_random_seed,
    track_movement,
    track_cumulative_movement,  # deprecated alias
)

__version__ = "0.7.0"

__all__ = [
    "__version__",
    # Core - ONE fitting function
    "fit_priority_matrix",
    # Utilities
    "set_glmm_random_seed",
    # Tracking
    "track_movement",
    "track_cumulative_movement",  # deprecated alias
    "load_or_track_movement",
    "extract_transitions",
    "extract_transition_drivers",
    "display_transition_drivers",
    # Visualization
    "plot_priority_matrix",
    "plot_transition_timeline",
    "layout_transition_labels",
    "plot_entity_trajectories",
    # Metrics
    "aggregate_entity_metrics",
    "add_priority_indices",
]
