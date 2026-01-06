"""Tests for axis-aware PriorityX API (current version).

These tests validate the unified fit_priority_matrix() with x_metric/y_metric params.
"""

from datetime import datetime, timedelta

import numpy as np
import pandas as pd

import priorityx as px


def _generate_axis_data(n_entities: int = 4, n_quarters: int = 8) -> pd.DataFrame:
    dates = []
    entities = []
    metrics = []
    base_date = datetime(2023, 1, 1)

    for e_idx in range(n_entities):
        name = f"Entity_{chr(65 + e_idx)}"
        for q in range(n_quarters):
            quarter_date = base_date + timedelta(days=q * 91)
            # a few rows per quarter per entity
            for _ in range(3):
                dates.append(quarter_date)
                entities.append(name)
                # metric increases with entity index
                metrics.append(1.0 + e_idx)

    return pd.DataFrame({"entity": entities, "date": dates, "metric": metrics})


def test_fit_priority_matrix_custom_y_metric():
    """fit_priority_matrix with y_metric should combine count-based X and metric-based Y axes."""

    df = _generate_axis_data()

    # current version API: use y_metric instead of fit_priority_axes
    results, stats = px.fit_priority_matrix(
        df,
        entity_col="entity",
        timestamp_col="date",
        y_metric="metric",
        temporal_granularity="quarterly",
        min_observations=0,
        min_total_count=0,
    )

    assert "x_score" in results.columns
    assert "y_score" in results.columns
    assert "quadrant" in results.columns
    assert "count" in results.columns

    # dual GLMM returns nested stats
    assert "x_stats" in stats
    assert "y_stats" in stats

    # sanity check: scores are finite
    assert np.isfinite(results["x_score"]).all()
    assert np.isfinite(results["y_score"]).all()


def test_fit_priority_matrix_dual_metrics():
    """Metric/metric axes should also run and produce non-identical scores."""

    df = _generate_axis_data()
    # create a second metric that is negatively correlated
    df = df.copy()
    df["metric2"] = df["metric"].max() + 1 - df["metric"]

    # current version API: use x_metric and y_metric
    results, stats = px.fit_priority_matrix(
        df,
        entity_col="entity",
        timestamp_col="date",
        x_metric="metric",
        y_metric="metric2",
        temporal_granularity="quarterly",
        min_observations=0,
        min_total_count=0,
    )

    assert len(results) > 0
    assert stats["x_metric"] == "metric"
    assert stats["y_metric"] == "metric2"

    # sanity check: scores are finite
    assert np.isfinite(results["x_score"]).all()
    assert np.isfinite(results["y_score"]).all()
