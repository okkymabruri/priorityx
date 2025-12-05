"""Public convenience API for PriorityX.

This module exposes the most commonly used functions via a compact
namespace so users can write:

    import priorityx as px
    results, stats = px.fit_priority_matrix(...)

without losing access to the more detailed submodules under
``priorityx.core``, ``priorityx.tracking``, or ``priorityx.viz``.
"""

from .core.glmm import fit_priority_matrix, set_glmm_random_seed
from .metrics import aggregate_entity_metrics, add_priority_indices
from .tracking.movement import track_cumulative_movement, load_or_track_movement
from .tracking.transitions import extract_transitions
from .tracking.drivers import (
    extract_transition_drivers,
    display_transition_drivers,
)
from .viz.matrix import plot_priority_matrix
from .viz.timeline import plot_transition_timeline
from .viz.trajectory import plot_entity_trajectories

# Thin alias for the common GLMM fit path.
fit = fit_priority_matrix


__all__ = [
    "fit_priority_matrix",
    "fit",
    "set_glmm_random_seed",
    "track_cumulative_movement",
    "load_or_track_movement",
    "extract_transitions",
    "extract_transition_drivers",
    "display_transition_drivers",
    "plot_priority_matrix",
    "plot_transition_timeline",
    "plot_entity_trajectories",
    "aggregate_entity_metrics",
    "add_priority_indices",
]
