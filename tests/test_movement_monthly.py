"""Smoke tests for monthly movement and basic viz integration."""

from datetime import datetime, timedelta

import pandas as pd

from priorityx.tracking.movement import track_cumulative_movement
from priorityx.tracking.transitions import extract_transitions
from priorityx.viz.timeline import plot_transition_timeline
from priorityx.viz.trajectory import plot_entity_trajectories


def _generate_monthly_data(n_entities: int = 3, n_months: int = 12) -> pd.DataFrame:
    """Generate synthetic monthly data for movement tests."""

    base_date = datetime(2023, 1, 1)
    rows: list[dict] = []

    for e_idx in range(n_entities):
        entity = f"Entity_{e_idx+1}"
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

    movement_df, meta = track_cumulative_movement(
        df,
        entity_col="entity",
        timestamp_col="date",
        quarters=None,
        min_total_count=10,
        temporal_granularity="monthly",
    )

    assert not movement_df.empty
    assert meta["temporal_granularity"] == "monthly"
    assert "entity" in movement_df.columns
    assert "quarter" in movement_df.columns


def test_monthly_timeline_smoke():
    """Monthly transitions + timeline should run without errors."""

    df = _generate_monthly_data()

    movement_df, _ = track_cumulative_movement(
        df,
        entity_col="entity",
        timestamp_col="date",
        quarters=None,
        min_total_count=10,
        temporal_granularity="monthly",
    )

    transitions = extract_transitions(movement_df)

    if transitions.empty:
        return

    fig = plot_transition_timeline(
        transitions,
        entity_name="Entity",
        x_axis_granularity="monthly",
        temporal_granularity="monthly",
        movement_df=movement_df,
        save_plot=False,
        save_csv=False,
        close_fig=True,
    )

    assert fig is not None


def test_monthly_trajectories_smoke():
    """Monthly trajectories should run without errors."""

    df = _generate_monthly_data()

    movement_df, _ = track_cumulative_movement(
        df,
        entity_col="entity",
        timestamp_col="date",
        quarters=None,
        min_total_count=10,
        temporal_granularity="monthly",
    )

    fig = plot_entity_trajectories(
        movement_df,
        entity_name="Entity",
        temporal_granularity="monthly",
        save_plot=False,
        save_csv=False,
        close_fig=True,
    )

    assert fig is not None
