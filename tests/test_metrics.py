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
            "Random_Slope": [0.1, 0.2],
            "total_primary": [300.0, 50.0],
            "mean_duration": [5.0, 10.0],
            "secondary_to_primary_ratio": [0.5, 0.8],
        }
    )

    out = px.add_priority_indices(df)

    # z-scored components
    for col in [
        "z_count",
        "z_Random_Slope",
        "z_total_primary",
        "z_neg_duration",
        "z_ratio",
    ]:
        assert col in out.columns

    # composite indices
    assert "volume_growth_index" in out.columns
    assert "service_quality_index" in out.columns
    assert "early_warning_index" in out.columns
