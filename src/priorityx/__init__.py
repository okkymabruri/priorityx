"""priorityx: Entity prioritization and escalation detection using GLMM statistical models.

The :mod:`priorityx.api` module exposes a small convenience facade so
users can write::

    import priorityx as px
    results, stats = px.fit_priority_matrix(...)

while more advanced workflows can continue to import from the
``core``, ``tracking`` and ``viz`` subpackages directly.
"""

from .api import (  # noqa: F401
    display_transition_drivers,
    extract_transition_drivers,
    extract_transitions,
    fit,
    fit_priority_matrix,
    load_or_track_movement,
    plot_entity_trajectories,
    plot_priority_matrix,
    plot_transition_timeline,
    set_glmm_random_seed,
    track_cumulative_movement,
)

__version__ = "0.3.0"

__all__ = [
    "__version__",
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
]

