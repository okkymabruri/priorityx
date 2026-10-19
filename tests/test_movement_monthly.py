"""Smoke tests for monthly movement and basic viz integration."""

from datetime import datetime, timedelta

import pandas as pd
import numpy as np
import pytest
from pathlib import Path

import priorityx as px
from test_results import frames


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


def test_track_cumulative_movement_monthly_basic(tmp_path, monkeypatch):
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

    # Exercise CSV reuse with the actual maintained fit rather than a second fit.
    from priorityx.tracking import movement
    monkeypatch.setattr(movement, "track_movement", lambda *args, **kwargs: movement_df)
    options = dict(entity_name="Service", entity_col="entity", timestamp_col="date",
                   quarters=None, min_total_count=10, temporal_granularity="monthly", output_dir=str(tmp_path))
    px.load_or_track_movement(df, **options)
    cached = px.load_or_track_movement(df, **options)
    pd.testing.assert_frame_equal(cached, movement_df.reset_index(drop=True), check_exact=True)


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


@pytest.fixture
def movement_cache(monkeypatch, tmp_path):
    """Exercise real caching around existing raw/result fixtures, without fitting."""
    from priorityx.tracking import movement
    from priorityx.core import glmm

    raw = _generate_monthly_data()
    raw["alternate_entity"] = raw["entity"]
    raw["alternate_date"] = raw["date"]
    calls = []
    monkeypatch.setattr(glmm, "_GLMM_RANDOM_SEED", None)
    monkeypatch.setattr(glmm, "_GLMM_SEED_APPLIED", False)

    def track(data, **kwargs):
        calls.append(kwargs)
        result = frames(kwargs["temporal_granularity"])[1].rename(columns={"month": "quarter"})
        result["period_x"] = np.nextafter(1.0, 2.0) * len(calls)
        result["period_count"] = np.nan
        result["quadrant_differs"] = False
        return result

    monkeypatch.setattr(movement, "track_movement", track)
    options = dict(entity_name="Service", entity_col="entity", timestamp_col="date",
                   quarters=None, min_total_count=20, output_dir=str(tmp_path))
    return raw, options, calls


@pytest.mark.parametrize("cadence", ["quarterly", "monthly"])
def test_movement_cache_roundtrip_reuses_exact_request_and_preserves_input(movement_cache, cadence):
    raw, options, calls = movement_cache
    options["temporal_granularity"] = cadence
    original = raw.copy(deep=True)
    first, path = px.load_or_track_movement(raw, **options, return_path=True)
    before = Path(path).read_bytes(), Path(path).stat().st_mtime_ns
    cached = px.load_or_track_movement(raw, **dict(reversed(list(options.items()))))
    _, same_path = px.load_or_track_movement(raw, **options, return_path=True)
    assert len(calls) == 1 and same_path == path
    assert (Path(path).read_bytes(), Path(path).stat().st_mtime_ns) == before
    pd.testing.assert_frame_equal(cached, first, check_exact=True)
    pd.testing.assert_frame_equal(raw, original)
    assert cached.loc[0, "entity"] == "001"
    assert ("month" if cadence == "monthly" else "quarter") in Path(path).read_text().splitlines()[0].split(",")
    assert "quarter" in cached.columns and "month" not in cached.columns
    assert {k: calls[0][k] for k in ("decline_window_quarters", "vcp_p", "fe_p")} == {
        "decline_window_quarters": 6, "vcp_p": 3.5, "fe_p": 3.0,
    }


@pytest.mark.parametrize("change", ["data", "filter", "column", "dtype", "index", "entity_mapping", "date_mapping",
                                     "schedule", "threshold", "cadence", "decline", "vcp", "fe", "seed", "version"])
def test_movement_cache_invalidates_changed_requests_and_keeps_previous(movement_cache, monkeypatch, change):
    raw, options, calls = movement_cache
    _, previous_path = px.load_or_track_movement(raw, **options, return_path=True)
    previous_bytes = Path(previous_path).read_bytes()
    changed_raw, changed_options = raw.copy(deep=True), options.copy()
    with monkeypatch.context() as patch:
        if change == "data":
            changed_raw.loc[0, "entity"] = "changed"
        elif change == "filter":
            changed_raw = changed_raw.iloc[5:]
        elif change == "column":
            changed_raw = changed_raw.rename(columns={"alternate_entity": "unused_entity"})
        elif change == "dtype":
            changed_raw["entity"] = changed_raw["entity"].astype("category")
        elif change == "index":
            changed_raw.index = changed_raw.index + 100
        elif change == "entity_mapping":
            changed_options["entity_col"] = "alternate_entity"
        elif change == "date_mapping":
            changed_options["timestamp_col"] = "alternate_date"
        elif change == "schedule":
            changed_options["quarters"] = [("2023-Q1", "2023-04-01")]
        elif change == "threshold":
            changed_options["min_total_count"] = 50
        elif change == "cadence":
            changed_options["temporal_granularity"] = "monthly"
        elif change == "decline":
            changed_options["decline_window_quarters"] = 4
        elif change == "vcp":
            changed_options["vcp_p"] = 2.5
        elif change == "fe":
            changed_options["fe_p"] = 2.0
        elif change == "seed":
            px.set_glmm_random_seed(1234)
        elif change == "version":
            patch.setattr(px, "__version__", "next")
        _, current_path = px.load_or_track_movement(changed_raw, **changed_options, return_path=True)
        assert current_path != previous_path
        assert len(calls) == 2
        # Seed setters affect the live configuration, not just the environment.
        if change == "seed":
            px.set_glmm_random_seed(None)
    _, reused_path = px.load_or_track_movement(raw, **options, return_path=True)
    assert reused_path == previous_path and len(calls) == 2
    assert Path(previous_path).read_bytes() == previous_bytes


@pytest.mark.parametrize("cadence", ["quarterly", "monthly"])
def test_movement_cache_resolves_equivalent_schedules_and_forwards_options(movement_cache, cadence):
    from priorityx.tracking.movement import normalize_period_schedule

    raw, options, calls = movement_cache
    options.update(temporal_granularity=cadence, decline_window_quarters=4, vcp_p=2.5, fe_p=2.0)
    _, first_path = px.load_or_track_movement(raw, **options, return_path=True)
    schedule = normalize_period_schedule(None, raw, "date", cadence)
    options["quarters"] = schedule
    _, explicit_path = px.load_or_track_movement(raw, **options, return_path=True)
    options["quarters"] = [(label, cutoff + " 00:00:00") for label, cutoff in schedule]
    _, equivalent_path = px.load_or_track_movement(raw, **options, return_path=True)
    options["quarters"] = ["2023-01-01", schedule[-1][1]]
    _, range_path = px.load_or_track_movement(raw, **options, return_path=True)
    assert first_path == explicit_path == equivalent_path == range_path and len(calls) == 1
    assert calls[0]["quarters"] == schedule
    assert {k: calls[0][k] for k in ("decline_window_quarters", "vcp_p", "fe_p")} == {
        "decline_window_quarters": 4, "vcp_p": 2.5, "fe_p": 2.0,
    }


def test_movement_cache_force_refresh_only_replaces_matching_key(movement_cache):
    raw, options, calls = movement_cache
    _, original_path = px.load_or_track_movement(raw, **options, return_path=True)
    original_bytes = Path(original_path).read_bytes()
    changed = {**options, "min_total_count": 50}
    _, other_path = px.load_or_track_movement(raw, **changed, return_path=True)
    other_bytes = Path(other_path).read_bytes()
    fresh, fresh_path = px.load_or_track_movement(raw, **options, use_cache=False, return_path=True)
    assert len(calls) == 3 and fresh_path == original_path
    assert Path(original_path).read_bytes() != original_bytes
    assert Path(other_path).read_bytes() == other_bytes
    pd.testing.assert_frame_equal(px.load_or_track_movement(raw, **options), fresh, check_exact=True)
    assert len(calls) == 3
    assert sorted(path.suffix for path in Path(options["output_dir"]).iterdir()) == [".csv", ".csv"]


@pytest.mark.parametrize("failure", ["fit", "serialize", "replace"])
def test_movement_cache_failed_refresh_preserves_previous_file(movement_cache, monkeypatch, failure):
    from priorityx.tracking import movement
    from priorityx.utils import helpers

    raw, options, _ = movement_cache
    _, path = px.load_or_track_movement(raw, **options, return_path=True)
    previous = Path(path).read_bytes(), Path(path).stat().st_mtime_ns

    def fail(*args, **kwargs):
        if failure == "serialize":
            args[1].write("partial write")
        raise RuntimeError("deliberate failure")

    if failure == "fit":
        monkeypatch.setattr(movement, "track_movement", fail)
    elif failure == "serialize":
        monkeypatch.setattr(pd.DataFrame, "to_csv", fail)
    else:
        monkeypatch.setattr(helpers.os, "replace", fail)
    with pytest.raises(RuntimeError, match="deliberate failure"):
        px.load_or_track_movement(raw, **options, use_cache=False)
    assert (Path(path).read_bytes(), Path(path).stat().st_mtime_ns) == previous
    assert list(Path(options["output_dir"]).iterdir()) == [Path(path)]


@pytest.mark.parametrize("cadence", ["quarterly", "monthly"])
def test_movement_cache_ignores_and_preserves_legacy_date_only_csv(movement_cache, cadence):
    raw, options, calls = movement_cache
    options["temporal_granularity"] = cadence
    suffix = "M" if cadence == "monthly" else "Q"
    legacy = Path(options["output_dir"]) / f"movement-service-{suffix}-20990101.csv"
    # Preserve even the older Monthly spelling instead of rewriting its header.
    legacy.write_text("entity,quarter\n001,2025-01\n")
    before = legacy.read_bytes(), legacy.stat().st_mtime_ns
    _, path = px.load_or_track_movement(raw, **options, return_path=True)
    assert len(calls) == 1 and Path(path) != legacy
    assert (legacy.read_bytes(), legacy.stat().st_mtime_ns) == before


@pytest.mark.parametrize("content", [b"\xff", b"not,a,movement\n1,2,3\n",
                                    b"entity,quarter,period_x,period_y,period_quadrant,global_quadrant\n001,2025-Q1,bad,1,Q1,Q1\n"])
def test_unreadable_movement_cache_errors_without_fitting(movement_cache, content):
    raw, options, calls = movement_cache
    _, path = px.load_or_track_movement(raw, **options, return_path=True)
    Path(path).write_bytes(content)
    with pytest.raises(ValueError, match="Cannot read movement cache.*use_cache=False"):
        px.load_or_track_movement(raw, **options)
    assert len(calls) == 1 and Path(path).read_bytes() == content


@pytest.mark.parametrize("empty", [False, True])
def test_movement_cache_preserves_text_identifiers_and_empty_schema(movement_cache, monkeypatch, empty):
    from priorityx.tracking import movement

    raw, options, _ = movement_cache
    result = frames("quarterly")[1]
    result = pd.concat([result.assign(entity=value) for value in ("001", "NA", "nan", "")], ignore_index=True)
    if empty:
        result = result.iloc[:0]
    monkeypatch.setattr(movement, "track_movement", lambda *args, **kwargs: result)
    px.load_or_track_movement(raw, **options)
    cached = px.load_or_track_movement(raw, **options)
    assert cached["entity"].tolist() == result["entity"].tolist()
    assert cached.columns.tolist() == result.columns.tolist()
    if not empty:
        pd.testing.assert_frame_equal(cached, result, check_exact=True)
