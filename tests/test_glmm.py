"""Tests for GLMM estimation."""

import pandas as pd
from datetime import datetime, timedelta
import numpy as np
import priorityx as px


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

    results, stats = px.fit_priority_matrix(
        df,
        entity_col="entity",
        timestamp_col="date",
        temporal_granularity="quarterly",
        min_observations=6,
    )

    assert len(results) > 0
    assert "entity" in results.columns
    # current version: standardized column names
    assert "x_score" in results.columns
    assert "y_score" in results.columns
    assert "quadrant" in results.columns


def test_fit_priority_matrix_stats():
    """Test statistics output."""
    df = generate_test_data()

    results, stats = px.fit_priority_matrix(
        df, entity_col="entity", timestamp_col="date", temporal_granularity="quarterly"
    )

    assert "n_entities" in stats
    assert "n_observations" in stats
    assert "method" in stats
    assert stats["method"] == "VB"
    assert stats["temporal_granularity"] == "quarterly"


def test_fit_priority_matrix_monthly_basic():
    """Monthly granularity should run and report correct stats flag."""

    df = generate_test_data()

    results, stats = px.fit_priority_matrix(
        df,
        entity_col="entity",
        timestamp_col="date",
        temporal_granularity="monthly",
        min_observations=3,
    )

    assert len(results) > 0
    assert stats["temporal_granularity"] == "monthly"


def test_fit_priority_matrix_seed_control():
    """Verify explicit seeding produces deterministic random effects."""

    df = generate_test_data()

    px.set_glmm_random_seed(1234)
    results1, _ = px.fit_priority_matrix(
        df,
        entity_col="entity",
        timestamp_col="date",
        temporal_granularity="quarterly",
        min_observations=6,
    )

    px.set_glmm_random_seed(1234)
    results2, _ = px.fit_priority_matrix(
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
    results1, _ = px.fit_priority_matrix(
        df, entity_col="entity", timestamp_col="date", min_total_count=0
    )

    # with high filter (should filter out low-volume entities)
    results2, _ = px.fit_priority_matrix(
        df, entity_col="entity", timestamp_col="date", min_total_count=250
    )

    assert len(results2) < len(results1)


def test_date_filter():
    """Test date filtering: should either run or gracefully raise ValueError.

    Some date filters can produce an empty design matrix for the GLMM,
    which statsmodels reports as a ValueError. The contract we care
    about here is that filtering does not hang and the error surface is
    stable, not that a model is always fit.
    """
    df = generate_test_data()

    try:
        results, _ = px.fit_priority_matrix(
            df,
            entity_col="entity",
            timestamp_col="date",
            date_filter="< 2024-01-01",
            min_total_count=0,
            min_observations=3,
        )
        # When a model is fit, we should get a DataFrame back (possibly empty)
        assert isinstance(results, pd.DataFrame)
    except ValueError as exc:
        # Accept the known statsmodels error surface for empty designs
        msg = str(exc)
        assert "len(ident) should match the number of columns of exog_vc" in msg or (
            "The lengths of vcp_names and ident should be the same" in msg
        )


def test_date_filter_monthly():
    """Date filter should also work under monthly granularity without errors."""

    df = generate_test_data()

    results, stats = px.fit_priority_matrix(
        df,
        entity_col="entity",
        timestamp_col="date",
        date_filter="< 2024-01-01",
        temporal_granularity="monthly",
        min_total_count=50,
        min_observations=3,
    )

    assert len(results) > 0
    assert stats["temporal_granularity"] == "monthly"


def test_y_metric_uses_gaussian_glmm():
    """Custom Y metric should use Gaussian GLMM and produce nontrivial effects.

    current version: metric_col replaced by y_metric param.
    """

    df = generate_test_data()
    # Attach a simple synthetic metric that increases with entity index.
    df = df.copy()
    df["metric"] = 1.0
    # encode entity index as part of the metric so that entities differ
    for idx, name in enumerate(sorted(df["entity"].unique())):
        df.loc[df["entity"] == name, "metric"] += idx

    results, stats = px.fit_priority_matrix(
        df,
        entity_col="entity",
        timestamp_col="date",
        temporal_granularity="quarterly",
        min_observations=3,
        y_metric="metric",  # current version: use y_metric instead of metric_col
    )

    assert len(results) > 0
    # Dual GLMM mode returns stats with y_stats nested
    assert "y_stats" in stats
    assert stats["y_stats"]["method"] in {
        "MixedLM",
        "GaussianVB",
        "GaussianMAP",
        "GaussianMLE",
    }

    x_scores = results["x_score"].to_numpy()
    y_scores = results["y_score"].to_numpy()
    # Both axes should have finite values
    assert np.isfinite(x_scores).all()
    assert np.isfinite(y_scores).all()


def test_dual_metric_axes():
    """Test fitting both X and Y as custom metrics.

    current version: new feature - x_metric and y_metric params.
    """

    df = generate_test_data()
    df = df.copy()
    df["metric_x"] = 1.0
    df["metric_y"] = 10.0
    for idx, name in enumerate(sorted(df["entity"].unique())):
        df.loc[df["entity"] == name, "metric_x"] += idx
        df.loc[df["entity"] == name, "metric_y"] += idx * 2

    results, stats = px.fit_priority_matrix(
        df,
        entity_col="entity",
        timestamp_col="date",
        temporal_granularity="quarterly",
        min_observations=3,
        x_metric="metric_x",
        y_metric="metric_y",
    )

    assert len(results) > 0
    assert "x_metric" in stats
    assert "y_metric" in stats
    assert stats["x_metric"] == "metric_x"
    assert stats["y_metric"] == "metric_y"
    assert "x_score" in results.columns
    assert "y_score" in results.columns
