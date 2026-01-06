"""priorityx: Entity prioritization and escalation detection using GLMM statistical models.

The :mod:`priorityx.api` module exposes a small convenience facade so
users can write::

    import priorityx as px
    results, stats = px.fit_priority_matrix(...)

while more advanced workflows can continue to import from the
``core``, ``tracking`` and ``viz`` subpackages directly.

## current version API (consolidated)

The unified API uses ``fit_priority_matrix()`` as THE single entry point:

    # Default: volume x growth
    results, stats = px.fit_priority_matrix(df, entity_col="service", timestamp_col="date")

    # Custom Y axis: volume x resolution_days
    results, stats = px.fit_priority_matrix(df, ..., y_metric="resolution_days")

    # Custom both axes: disputed x paid
    results, stats = px.fit_priority_matrix(df, ..., x_metric="disputed", y_metric="paid")

Return columns: entity, x_score, y_score, count, quadrant
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
    set_glmm_random_seed,
    track_cumulative_movement,
)

__version__ = "0.4.0"

__all__ = [
    "__version__",
    # Core - ONE fitting function
    "fit_priority_matrix",
    # Utilities
    "set_glmm_random_seed",
    # Tracking
    "track_cumulative_movement",
    "load_or_track_movement",
    "extract_transitions",
    "extract_transition_drivers",
    "display_transition_drivers",
    # Visualization
    "plot_priority_matrix",
    "plot_transition_timeline",
    "plot_entity_trajectories",
    # Metrics
    "aggregate_entity_metrics",
    "add_priority_indices",
]
