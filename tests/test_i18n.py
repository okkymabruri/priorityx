"""Regression tests for additive English/Indonesian chart localization."""

import copy

import matplotlib
matplotlib.use("Agg")
import pandas as pd
import pytest

import priorityx as px
from priorityx.app import build_html
from priorityx.i18n import catalog, text, validate_language
from priorityx.views import ViewSettings, prepare_bundle, resolve_settings
from priorityx.viz.export import render_static
from test_results import frames
from test_views import bundle


def test_catalog_supports_only_en_and_id():
    assert set(catalog()) == {"en", "id"}
    assert set(catalog()["en"]) == set(catalog()["id"])
    assert text("en", "chart_matrix") == "Quadrant matrix"
    assert text("id", "chart_matrix") == "Matriks kuadran"
    assert validate_language(None) == "en"
    with pytest.raises(ValueError, match="language"):
        validate_language("fr")


def test_matplotlib_localization_preserves_matrix_geometry_and_custom_labels():
    matrix, _, transitions = frames("quarterly")
    english = px.plot_priority_matrix(matrix, language="en")
    indonesian = px.plot_priority_matrix(matrix, language="id")
    assert indonesian.axes[0].get_xlim() == english.axes[0].get_xlim()
    assert indonesian.axes[0].get_ylim() == english.axes[0].get_ylim()
    assert indonesian.axes[0].get_xlabel() == "Volume (Relatif)"
    assert indonesian.axes[0].get_ylabel() == "Laju Pertumbuhan (Relatif)"
    assert indonesian.axes[0].get_title().endswith("Matriks Prioritas")
    assert [point.get_offsets().tolist() for point in indonesian.axes[0].collections] == [
        point.get_offsets().tolist() for point in english.axes[0].collections
    ]

    custom = px.plot_priority_matrix(
        matrix,
        x_label="Custom X",
        y_label="Custom Y",
        title="Caller title",
        language="id",
    )
    assert custom.axes[0].get_xlabel() == "Custom X"
    assert custom.axes[0].get_ylabel() == "Custom Y"
    assert custom.axes[0].get_title() == "Caller title"
    english.clear()
    indonesian.clear()
    custom.clear()

    timeline = px.plot_transition_timeline(transitions, language="id")
    assert timeline.axes[0].get_xlabel() == "Kuartal"
    assert timeline.axes[0].get_title().endswith("Linimasa Transisi")
    timeline.clear()


def test_trajectory_localization_keeps_coordinates_and_machine_values():
    movement = pd.DataFrame({
        "entity": ["A", "A", "B", "B"],
        "quarter": ["2025-Q1", "2025-Q2", "2025-Q1", "2025-Q2"],
        "period_x": [1.0, 2.0, -1.0, -2.0],
        "period_y": [1.0, 2.0, -1.0, -2.0],
        "global_quadrant": ["Q1", "Q1", "Q3", "Q3"],
        "x_delta": [0.0, 1.0, 0.0, -1.0],
        "y_delta": [0.0, 1.0, 0.0, -1.0],
    })
    english = px.plot_entity_trajectories(movement, language="en", max_entities=2)
    indonesian = px.plot_entity_trajectories(movement, language="id", max_entities=2)
    assert indonesian.axes[0].get_xlabel() == "Volume (Relatif)"
    assert indonesian.axes[0].get_ylabel() == "Laju Pertumbuhan (Relatif)"
    assert indonesian.axes[0].get_title().endswith("Trajektori Entitas")
    assert [line.get_xydata().tolist() for line in indonesian.axes[0].lines] == [
        line.get_xydata().tolist() for line in english.axes[0].lines
    ]
    english.clear()
    indonesian.clear()


def test_view_language_round_trip_static_geometry_and_offline_catalog():
    source = bundle()
    before = copy.deepcopy(source.to_dict())
    prepared = prepare_bundle(source)
    settings = resolve_settings(None, prepared)
    assert settings.language == "en"
    legacy = settings.to_dict()
    legacy.pop("language")
    assert ViewSettings.from_dict(legacy, prepared).language == "en"

    settings.language = "id"
    figure, report = render_static(prepared["datasets"][0], settings, "matrix")
    english_settings = resolve_settings(None, prepared)
    english_figure, english_report = render_static(prepared["datasets"][0], english_settings, "matrix")
    assert report.to_dict()["dimensions"] == english_report.to_dict()["dimensions"]
    assert figure.axes[0].get_title() == "Matriks kuadran"
    assert source.to_dict() == before
    assert settings.to_dict()["language"] == "id"
    figure.clear()
    english_figure.clear()

    html = build_html(source, settings=settings)
    assert "PRIORITYX_I18N" in html
    assert "Bahasa Indonesia" in html
