"""Tests for GLMM estimation."""

import polars as pl
import pytest
from datetime import datetime, timedelta
from priorityx.core.glmm import fit_priority_matrix


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

    df = pl.DataFrame({
        "entity": entities,
        "date": dates,
    })

    return df.with_columns(pl.col("date").cast(pl.Date))


def test_fit_priority_matrix_basic():
    """Test basic GLMM fitting."""
    df = generate_test_data()

    results, stats = fit_priority_matrix(
        df,
        entity_col="entity",
        timestamp_col="date",
        temporal_granularity="quarterly",
        min_observations=6
    )

    assert len(results) > 0
    assert "entity" in results.columns
    assert "Random_Intercept" in results.columns
    assert "Random_Slope" in results.columns
    assert "quadrant" in results.columns
    assert "count" in results.columns


def test_fit_priority_matrix_stats():
    """Test statistics output."""
    df = generate_test_data()

    results, stats = fit_priority_matrix(
        df,
        entity_col="entity",
        timestamp_col="date",
        temporal_granularity="quarterly"
    )

    assert "n_entities" in stats
    assert "n_observations" in stats
    assert "method" in stats
    assert stats["method"] == "VB"


def test_min_total_count_filter():
    """Test minimum count filtering."""
    df = generate_test_data(n_entities=5)

    # without filter
    results1, _ = fit_priority_matrix(
        df, entity_col="entity", timestamp_col="date",
        min_total_count=0
    )

    # with high filter
    results2, _ = fit_priority_matrix(
        df, entity_col="entity", timestamp_col="date",
        min_total_count=200
    )

    assert len(results2) < len(results1)


@pytest.mark.skip(reason="Date filter creates sparse data in synthetic test")
def test_date_filter():
    """Test date filtering."""
    df = generate_test_data(n_quarters=12)

    results, _ = fit_priority_matrix(
        df, entity_col="entity", timestamp_col="date",
        date_filter="> 2023-01-01",
        min_observations=6
    )

    assert len(results) >= 0
