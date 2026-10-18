"""Saved-result renderer semantics; reuse the maintained result-frame fixture."""
import copy
import io

import pytest

from priorityx.results import ResultBundle, ResultDataset, ResultValidationError
from priorityx.views import ViewSettings, prepare_bundle, resolve_settings
from priorityx.viz.export import render_static
from test_results import frames


def bundle(cadence="quarterly"):
    matrix, movement, transitions = frames(cadence)
    first, last = ("2025-Q1", "2025-Q4") if cadence == "quarterly" else ("2025-01", "2025-12")
    return ResultBundle([ResultDataset("item", cadence, "source", first, last,
                                      type_label="Work units", matrix=matrix,
                                      movement=movement, transitions=transitions)])


@pytest.mark.parametrize("cadence", ["monthly", "quarterly"])
def test_semantic_payload_is_deterministic_full_history_and_source_preserving(cadence):
    source = bundle(cadence)
    before = copy.deepcopy(source.to_dict())
    prepared = prepare_bundle(source)
    assert prepared == prepare_bundle(source)
    assert source.to_dict() == before
    dataset = prepared["datasets"][0]
    assert dataset["matrix"][0] == {"entity": "001", "x": 1.0, "y": 2.0, "count": 3, "quadrant": "Q1"}
    assert dataset["events"] == [{"entity": "001", "period": before["datasets"][0]["transitions"]["records"][0]["transition_quarter"],
                                    "source": "2", "destination": "1", "suffix": "*XY", "class": 2}]
    assert dataset["typeLabel"] == "Work units"
    assert dataset["rows"] == ["001"] and dataset["defaultPaths"] == ["001"]
    assert "Investigate" in " ".join(dataset["warnings"])
    assert len(dataset["periods"]) == (12 if cadence == "monthly" else 4)


def test_settings_reject_stale_unknown_nonfinite_and_invalid_view_inputs():
    prepared = prepare_bundle(bundle())
    settings = resolve_settings(None, prepared)
    assert settings.cadence == "quarterly"
    for changes in ({"bundle_id": "stale"}, {"extra": True}, {"schema_version": 2},
                    {"timeline_scale": float("nan")}, {"panel_height": True},
                    {"static_width": 100}, {"member": "absent"}, {"cadence": "monthly"},
                    {"views": {"unknown": {}}}):
        with pytest.raises(ResultValidationError):
            ViewSettings.from_dict({**settings.to_dict(), **changes}, prepared)
    state = settings.to_dict()
    key = prepared["datasets"][0]["key"]
    state["views"] = {key: {"ranges": {"matrix": {"x": [-1, 1], "y": [-2, 2]}},
                            "timeline": {"left": 42, "top": 0}, "focus": "matrix"}}
    assert resolve_settings(state, prepared).to_dict() == state
    # Version 1 files from the independent-fold UI remain valid.
    legacy = {**state, "views": {key: {"disclosures": {"timeline-data": True, "layout-settings": True}}}}
    assert resolve_settings(legacy, prepared).to_dict() == legacy
    current = {**state, "views": {key: {"data_tab": "paths", "paths_scope": "all",
                                         "disclosures": {"data-panel": True, "details": False},
                                         "tables": {"paths": 140}}}}
    assert resolve_settings(current, prepared).to_dict() == current
    for interaction in ({"ranges": {"matrix": {}}}, {"ranges": {"matrix": {"x": [1, -1], "y": [0, 1]}}},
                        {"timeline": {"top": "42"}}, {"row_left": -1}, {"focus": "unknown"},
                        {"disclosures": {"details": "true"}}, {"tables": {"matrix": float("inf")}},
                        {"data_tab": "missing"}, {"paths_scope": "missing"}, {"data_tab": []}, {"paths_scope": {}},
                        {"disclosures": {"data-panel": 1}}):
        with pytest.raises(ResultValidationError):
            resolve_settings({**state, "views": {key: interaction}}, prepared)
    for key in ("panel_height", "min_panel_width", "dpi"):
        with pytest.raises(ResultValidationError):
            resolve_settings({**settings.to_dict(), key: settings.to_dict()[key] + .5}, prepared)
    wide = {**settings.to_dict(), "layout_mode": "manual", "static_width": 40, "static_height": 30}
    assert resolve_settings(wide, prepared).static_width == 40
    assert resolve_settings(None, prepare_bundle(bundle("monthly"))).cadence == "monthly"


def test_absent_charts_and_explicit_saved_selections():
    source = bundle()
    source.datasets[0].selections = {"timeline_entities": [], "trajectory_entities": [], "trajectory_periods": 4}
    prepared = prepare_bundle(source)
    assert prepared["datasets"][0]["rows"] == []
    assert prepared["datasets"][0]["defaultPaths"] == []
    assert prepared["datasets"][0]["pathWindow"] == 4
    assert len(prepared["datasets"][0]["pathPeriods"]) == 4
    source.datasets[0].selections["trajectory_periods"] = 0
    with pytest.raises(ResultValidationError):
        prepare_bundle(source)
    empty = ResultBundle([ResultDataset("item", "quarterly", "source", "2025-Q1", "2025-Q4")])
    prepared_empty = prepare_bundle(empty)
    assert not any(prepared_empty["datasets"][0]["availability"].values())
    with pytest.raises(ResultValidationError, match="unavailable"):
        render_static(prepared_empty["datasets"][0], resolve_settings(None, prepared_empty), "matrix")


@pytest.mark.parametrize("cadence", ["monthly", "quarterly"])
def test_trajectory_defaults_rank_visible_trend_changes_with_stable_ties(cadence):
    import pandas as pd
    source = bundle(cadence)
    dataset = source.datasets[0]
    period = "month" if cadence == "monthly" else "quarter"
    periods = (["2025-01", "2025-11", "2025-12"] if cadence == "monthly"
               else ["2025-Q1", "2025-Q3", "2025-Q4"])
    histories = {"004": [0, 5, 6], "003": [0, 1, 2], "002": [0, -4, -6], "001": [0, 5, 6]}
    original = dataset.movement.iloc[[0]]
    dataset.movement = pd.concat([
        original.assign(entity=entity, **{period: p, "period_y": value})
        for entity, values in histories.items() for p, value in zip(periods, values)
    ], ignore_index=True)
    dataset.selections = {"trajectory_periods": 2}
    before = copy.deepcopy(source.to_dict())
    prepared = prepare_bundle(source)["datasets"][0]
    assert prepared["defaultPaths"] == ["001", "002", "004"]
    assert prepared["trajectorySelection"] == {"mode": "trend_change", "scores": {"001": 6, "002": 6, "004": 6}}
    assert source.to_dict() == before
    dataset.movement = dataset.movement.iloc[::-1].reset_index(drop=True)
    assert prepare_bundle(source)["datasets"][0]["defaultPaths"] == prepared["defaultPaths"]
    dataset.selections["trajectory_entities"] = ["003", "001"]
    explicit = prepare_bundle(source)["datasets"][0]
    assert explicit["defaultPaths"] == ["003", "001"]
    assert explicit["trajectorySelection"]["mode"] == "saved"
    dataset.movement = dataset.movement[dataset.movement[period] == periods[0]]
    del dataset.selections["trajectory_entities"]
    assert prepare_bundle(source)["datasets"][0]["defaultPaths"] == []


@pytest.mark.parametrize("family", ["matrix", "timeline", "paths"])
def test_static_export_uses_shared_saved_values_and_manual_size(family):
    prepared = prepare_bundle(bundle())
    settings = resolve_settings(None, prepared)
    settings.static_width, settings.static_height = 8, 6
    figure, report = render_static(prepared["datasets"][0], settings, family)
    assert tuple(figure.get_size_inches()) == (8, 6)
    assert report.to_dict()["dimensions"] == {"width_inches": 8, "height_inches": 6, "dpi": 150}
    assert report.bundle_id == prepared["bundle_id"]
    buffer = io.BytesIO()
    figure.savefig(buffer, format="png")
    assert buffer.getvalue().startswith(b"\x89PNG")
    if family == "timeline":
        assert [t.get_text() for t in figure.axes[0].get_xticklabels()] == prepared["datasets"][0]["periods"]
        assert "2→" in [t.get_text() for t in figure.axes[0].texts]
    else:
        # A ready report must not hide a label crossing a visible trajectory/axis.
        from matplotlib.text import Text
        renderer = figure.canvas.get_renderer()
        ax = figure.axes[0]
        assert report.unresolved == 0
        for text in ax.texts:
            assert not any(line.get_transform().transform_path(line.get_path()).intersects_bbox(
                Text.get_window_extent(text, renderer), filled=False) for line in ax.lines)
    figure.clear()


def test_display_window_and_risk_selection_do_not_replace_saved_history():
    source = bundle()
    source.datasets[0].as_of = "2026-Q1"
    before = copy.deepcopy(source.to_dict())
    prepared = prepare_bundle(source)
    assert prepared["datasets"][0]["periods"] == ["2026-Q1"]
    assert prepared["datasets"][0]["events"][0]["period"] == "2025-Q1"
    assert source.to_dict() == before
    source.datasets[0].selections = {"timeline_risk_levels": ["low"]}
    selected = prepare_bundle(source)["datasets"][0]
    assert selected["events"] == [] and selected["rows"] == []
    assert source.datasets[0].transitions.to_dict("records") == before["datasets"][0]["transitions"]["records"]
    source.datasets[0].selections = {"timeline_risk_levels": ["unknown"]}
    with pytest.raises(ResultValidationError, match="risk"):
        prepare_bundle(source)


def test_full_history_low_class_is_preserved_before_a_later_ytd_window():
    import pandas as pd
    matrix, movement, transitions = frames()
    # Reuse the existing saved-result frame at a second period: identical
    # coordinates/counts give a routine event under the established classifier.
    movement["cumulative_count"] = matrix.iloc[0]["count"]
    movement = pd.concat([movement, movement.assign(month="2025-02")], ignore_index=True)
    transitions = transitions.assign(transition_quarter="2025-02")
    source = ResultBundle([ResultDataset("item", "monthly", "source", "2025-01", "2026-01",
                                         matrix=matrix, movement=movement, transitions=transitions)])
    prepared = prepare_bundle(source)["datasets"][0]
    assert prepared["periods"] == ["2026-01"]
    assert prepared["events"][0]["class"] == 4
    assert prepared["events"][0]["suffix"] == "*XY"
    assert len(source.datasets[0].movement) == 2
