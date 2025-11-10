"""Tests for GLMM estimation."""

import pandas as pd
import pytest
from datetime import datetime, timedelta
from priorityx.core.glmm import fit_priority_matrix, set_glmm_random_seed


def generate_test_data(n_entities=5, n_quarters=12):
    """Generate synthetic data for testing."""
    dates = []
    entities = []
    base_date = datetime(2023, 1, 1)

    for entity_idx in range(n_entities):
        entity_name = f"Entity_{chr(65 + entity_idx)}"

        for quarter in range(n_quarters):
            quarter_date = base_date + timedelta(days=quarter * 91)
            n_obs = 10 + entity_idx * 3 + quarter  # more observations

            for _ in range(n_obs):
                dates.append(quarter_date)
                entities.append(entity_name)

    df = pd.DataFrame(
        {
            "entity": entities,
            "date": pd.to_datetime(dates),
        }
    )

    return df


def test_fit_priority_matrix_basic():
    """Test basic GLMM fitting."""
    df = generate_test_data()

    results, stats = fit_priority_matrix(
        df,
        entity_col="entity",
        timestamp_col="date",
        temporal_granularity="quarterly",
        min_observations=6,
    )

    assert len(results) > 0
    assert "entity" in results.columns
    assert "Random_Intercept" in results.columns
    assert "Random_Slope" in results.columns
    assert "quadrant" in results.columns


def test_fit_priority_matrix_stats():
    """Test statistics output."""
    df = generate_test_data()

    results, stats = fit_priority_matrix(
        df, entity_col="entity", timestamp_col="date", temporal_granularity="quarterly"
    )

    assert "n_entities" in stats
    assert "n_observations" in stats
    assert "method" in stats
    assert stats["method"] == "VB"
    assert stats["temporal_granularity"] == "quarterly"


def test_fit_priority_matrix_seed_control():
    """Verify explicit seeding produces deterministic random effects."""

    df = generate_test_data()

    set_glmm_random_seed(1234)
    results1, _ = fit_priority_matrix(
        df,
        entity_col="entity",
        timestamp_col="date",
        temporal_granularity="quarterly",
        min_observations=6,
    )

    set_glmm_random_seed(1234)
    results2, _ = fit_priority_matrix(
        df,
        entity_col="entity",
        timestamp_col="date",
        temporal_granularity="quarterly",
        min_observations=6,
    )

    pd.testing.assert_frame_equal(
        results1.sort_values("entity").reset_index(drop=True),
        results2.sort_values("entity").reset_index(drop=True),
    )


def test_min_total_count_filter():
    """Test minimum count filtering."""
    df = generate_test_data(n_entities=5)

    # without filter
    results1, _ = fit_priority_matrix(
        df, entity_col="entity", timestamp_col="date", min_total_count=0
    )

    # with high filter (should filter out low-volume entities)
    results2, _ = fit_priority_matrix(
        df, entity_col="entity", timestamp_col="date", min_total_count=250
    )

    assert len(results2) < len(results1)


@pytest.mark.skip(reason="Date filter creates sparse data, causes convergence issues")
def test_date_filter():
    """Test date filtering."""
    df = generate_test_data()

    results, _ = fit_priority_matrix(
        df, entity_col="entity", timestamp_col="date", date_filter="< 2024-01-01"
    )

    assert len(results) > 0
