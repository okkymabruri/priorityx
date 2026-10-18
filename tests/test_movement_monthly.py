"""Smoke tests for monthly movement and basic viz integration."""

from datetime import datetime, timedelta

import pandas as pd
import numpy as np
import pytest

import priorityx as px


def _generate_monthly_data(n_entities: int = 3, n_months: int = 12) -> pd.DataFrame:
    """Generate synthetic monthly data for movement tests."""

    base_date = datetime(2023, 1, 1)
    rows: list[dict] = []

    for e_idx in range(n_entities):
        entity = f"Entity_{e_idx + 1}"
        for m_idx in range(n_months):
            month_start = base_date + timedelta(days=30 * m_idx)
            n_obs = 5 + e_idx + m_idx // 2
            for _ in range(n_obs):
                rows.append({"entity": entity, "date": month_start})

    df = pd.DataFrame(rows)
    df["date"] = pd.to_datetime(df["date"])
    return df


def test_track_cumulative_movement_monthly_basic():
    """Monthly movement tracking should run and produce a non-empty DataFrame."""

    df = _generate_monthly_data()

    movement_df, meta = px.track_movement(
        df,
        entity_col="entity",
        timestamp_col="date",
        quarters=None,
        min_total_count=10,
        temporal_granularity="monthly",
        return_metadata=True,
    )

    assert not movement_df.empty
    assert meta["temporal_granularity"] == "monthly"
    assert "entity" in movement_df.columns
    assert "quarter" in movement_df.columns


def test_monthly_timeline_smoke():
    """Monthly transitions + timeline should run without errors."""

    df = _generate_monthly_data()

    movement_df = px.track_movement(
        df,
        entity_col="entity",
        timestamp_col="date",
        quarters=None,
        min_total_count=10,
        temporal_granularity="monthly",
    )

    transitions = px.extract_transitions(movement_df)

    if transitions.empty:
        return

    fig = px.plot_transition_timeline(
        transitions,
        entity_name="Product support units",
        x_axis_granularity="monthly",
        temporal_granularity="monthly",
        movement_df=movement_df,
        save_plot=False,
        save_csv=False,
        close_fig=True,
    )

    assert fig is not None
    assert fig.axes[0].get_ylabel() == "Product support units"
    assert fig.axes[0].get_title() == "Product support units Transition Timeline"


def test_monthly_trajectories_smoke():
    """Monthly trajectories should run without errors."""

    df = _generate_monthly_data()

    movement_df = px.track_movement(
        df,
        entity_col="entity",
        timestamp_col="date",
        quarters=None,
        min_total_count=10,
        temporal_granularity="monthly",
    )

    fig = px.plot_entity_trajectories(
        movement_df,
        entity_name="Product support units",
        temporal_granularity="monthly",
        save_plot=False,
        save_csv=False,
        close_fig=True,
    )

    assert fig is not None
    assert fig.axes[0].get_title() == "Product support units Entity Trajectory"


@pytest.mark.parametrize("monthly", [False, True])
def test_trajectories_accept_saved_last_active_metadata(monthly):
    """Existing saved activity metadata must not collide with trimming."""
    movement_df = pd.DataFrame(
        {
            "entity": ["A", "A", "B", "B"],
            "quarter": ["2023-01", "2023-02", "2023-01", "2023-02"],
            "period_count": [2, 1, 3, 0],
            "cumulative_count": [2, 3, 3, 3],
            "period_x": [0.1, 0.2, -0.1, -0.2],
            "period_y": [0.2, 0.3, -0.2, -0.1],
            "x_delta": [0.0, 0.1, 0.0, -0.1],
            "y_delta": [0.0, 0.1, 0.0, 0.1],
            "global_quadrant": ["Q1", "Q1", "Q3", "Q3"],
        }
    )
    if not monthly:
        movement_df["quarter"] = movement_df["quarter"].map({"2023-01": "2023-Q1", "2023-02": "2023-Q2"})
    saved = movement_df.copy()
    saved["last_active_quarter"] = saved.groupby("entity")["quarter"].transform("max")
    original = saved.copy(deep=True)
    fig = px.plot_entity_trajectories(
        saved,
        entity_name="Entity",
        save_plot=False,
        save_csv=False,
        close_fig=True,
    )
    assert fig is not None
    np.testing.assert_allclose(fig.axes[0].lines[0].get_xydata(), [[.1, .2], [.2, .3]])
    assert not any(text.get_text() == "B" for text in fig.axes[0].texts)
    without_metadata = px.plot_entity_trajectories(movement_df, close_fig=True)
    for actual, expected in zip(fig.axes[0].lines, without_metadata.axes[0].lines):
        np.testing.assert_allclose(actual.get_xydata(), expected.get_xydata())
    pd.testing.assert_frame_equal(saved, original)


def test_trajectories_highlight_top_n():
    """Test highlight_top_n param auto-selects top entities by trajectory distance."""

    df = _generate_monthly_data(n_entities=5, n_months=6)

    movement_df = px.track_movement(
        df,
        entity_col="entity",
        timestamp_col="date",
        quarters=None,
        min_total_count=5,
        temporal_granularity="monthly",
    )

    fig = px.plot_entity_trajectories(
        movement_df,
        entity_name="Entity",
        highlight_top_n=2,
        highlight_by="trajectory_distance",
        temporal_granularity="monthly",
        save_plot=False,
        save_csv=False,
        close_fig=True,
    )

    assert fig is not None


def test_trajectories_recent_periods():
    """Test recent_periods param limits trajectory window."""

    df = _generate_monthly_data(n_entities=3, n_months=12)

    movement_df = px.track_movement(
        df,
        entity_col="entity",
        timestamp_col="date",
        quarters=None,
        min_total_count=5,
        temporal_granularity="monthly",
    )

    fig = px.plot_entity_trajectories(
        movement_df,
        entity_name="Entity",
        highlight_top_n=2,
        recent_periods=4,
        temporal_granularity="monthly",
        save_plot=False,
        save_csv=False,
        close_fig=True,
    )

    assert fig is not None


def test_trajectories_highlight_by_total_movement():
    """Test highlight_by='total_movement' uses original selection logic."""

    df = _generate_monthly_data(n_entities=4, n_months=6)

    movement_df = px.track_movement(
        df,
        entity_col="entity",
        timestamp_col="date",
        quarters=None,
        min_total_count=5,
        temporal_granularity="monthly",
    )

    fig = px.plot_entity_trajectories(
        movement_df,
        entity_name="Entity",
        highlight_top_n=2,
        highlight_by="total_movement",
        temporal_granularity="monthly",
        save_plot=False,
        save_csv=False,
        close_fig=True,
    )

    assert fig is not None
