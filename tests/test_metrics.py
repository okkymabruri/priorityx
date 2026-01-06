"""Tests for per-entity metrics and indices helper functions."""

import pandas as pd

import priorityx as px


def test_aggregate_entity_metrics_basic():
    df = pd.DataFrame(
        {
            "entity": ["A", "A", "B"],
            "start_ts": ["2025-01-01", "2025-01-05", "2025-01-03"],
            "end_ts": [
                "2025-01-03",
                "2025-01-10",
                "2025-01-06",
            ],
            "primary": [100.0, 200.0, 50.0],
            "secondary": [50.0, 100.0, 10.0],
        }
    )

    metrics = px.aggregate_entity_metrics(
        df,
        entity_col="entity",
        duration_start_col="start_ts",
        duration_end_col="end_ts",
        primary_col="primary",
        secondary_col="secondary",
    )

    assert set(metrics["entity"]) == {"A", "B"}
    assert "mean_duration" in metrics.columns
    assert "total_primary" in metrics.columns
    assert "total_secondary" in metrics.columns
    assert "secondary_to_primary_ratio" in metrics.columns


def test_add_priority_indices_creates_indices():
    df = pd.DataFrame(
        {
            "entity": ["A", "B"],
            "count": [10, 20],
            "y_score": [0.1, 0.2],
            "total_amount": [300.0, 50.0],
            "mean_duration": [5.0, 10.0],
            "recovery_ratio": [0.5, 0.8],
        }
    )

    out = px.add_priority_indices(
        df,
        volume_col="count",
        growth_col="y_score",
        severity_col="total_amount",
        resolution_col="mean_duration",
        recovery_col="recovery_ratio",
    )

    # z-scored components (new naming: z_volume, z_growth, z_severity)
    for col in [
        "z_volume",
        "z_growth",
        "z_severity",
        "z_neg_resolution",
        "z_recovery",
    ]:
        assert col in out.columns

    # new composite indices
    assert "RI" in out.columns
    assert "SQI" in out.columns
    assert "EWI" in out.columns

    # legacy indices still available for backward compatibility
    assert "volume_growth_index" in out.columns
    assert "service_quality_index" in out.columns
    assert "early_warning_index" in out.columns
