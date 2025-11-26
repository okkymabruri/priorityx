"""Tests for transition driver analysis."""

import pandas as pd

from priorityx.tracking.drivers import (
    classify_priority,
    extract_transition_drivers,
    _calculate_quarter_dates,
)


def test_calculate_quarter_dates():
    """Test quarter date calculation."""
    start, end = _calculate_quarter_dates("2024-Q3")
    assert start == "2024-04-01"
    assert end == "2024-07-01"

    start, end = _calculate_quarter_dates("2025-Q1")
    assert start == "2024-10-01"
    assert end == "2025-01-01"


def test_classify_priority_critical():
    """Test critical priority classification."""
    priority, reason, spike = classify_priority(
        from_quadrant="Q3",
        to_quadrant="Q1",
        x=0.5,
        y=0.6,
        x_delta=0.5,
        y_delta=0.5,
        count_delta=100,
        percent_change=200,
    )
    assert priority == 1
    assert "Critical" in reason
    assert spike == "XY"


def test_classify_priority_investigate():
    """Test investigate priority."""
    priority, reason, spike = classify_priority(
        from_quadrant="Q3",
        to_quadrant="Q2",
        x=-0.1,
        y=0.2,
        x_delta=0.05,
        y_delta=0.2,
        count_delta=20,
        percent_change=150,
    )
    assert priority == 2
    assert spike is None


def test_extract_transition_drivers_basic():
    """Test basic transition driver extraction."""
    # create movement data
    movement_data = pd.DataFrame(
        {
            "entity": ["Service A", "Service A"],
            "quarter": ["2024-Q2", "2024-Q3"],
            "period_quadrant": ["Q3", "Q2"],
            "period_x": [-0.2, -0.1],
            "period_y": [-0.1, 0.2],
            "cumulative_count": [50, 80],
        }
    )

    # create raw data
    dates = pd.date_range(start="2024-01-01", end="2024-07-15", freq="D")

    df_raw = pd.DataFrame(
        {
            "service": ["Service A"] * len(dates),
            "date": dates,
            "type": ["Type1"] * (len(dates) // 2)
            + ["Type2"] * (len(dates) - len(dates) // 2),
        }
    )

    # run analysis
    analysis = extract_transition_drivers(
        movement_df=movement_data,
        df_raw=df_raw,
        entity_name="Service A",
        quarter_from="2024-Q2",
        quarter_to="2024-Q3",
        entity_col="service",
        timestamp_col="date",
    )

    # verify structure
    assert "transition" in analysis
    assert "magnitude" in analysis
    assert "priority" in analysis
    assert "subcategory_drivers" in analysis

    # verify transition data
    assert analysis["transition"]["entity"] == "Service A"
    assert analysis["transition"]["from_quadrant"] == "Q3"
    assert analysis["transition"]["to_quadrant"] == "Q2"
    assert analysis["transition"]["quadrant_changed"] is True
    assert "risk_level_change" in analysis["transition"]

    # verify magnitude
    assert analysis["magnitude"]["volume_change"]["count_from"] == 50
    assert analysis["magnitude"]["volume_change"]["count_to"] == 80
    assert analysis["magnitude"]["volume_change"]["absolute_delta"] == 30
    assert "weekly_avg_from" in analysis["magnitude"]["growth_change"]
    assert "period_counts" in analysis["magnitude"]

    # verify priority classification exists
    assert analysis["priority"]["priority"] in [1, 2, 3, 4]
    assert analysis["priority"]["priority_name"] in [
        "Critical",
        "Investigate",
        "Monitor",
        "Low",
    ]
    assert "spike_drivers" in analysis

    meta = analysis["meta"]
    assert meta["subcategory_columns_auto_detected"] is True
    assert meta["subcategory_columns_used"] == ["type"]
    assert meta["custom_driver_columns_loaded"] is False


def test_extract_transition_drivers_manual_subcategory_controls():
    """Ensure manual subcategory selection and knobs behave as expected."""

    movement_data = pd.DataFrame(
        {
            "entity": ["Service B", "Service B"],
            "quarter": ["2024-Q2", "2024-Q3"],
            "period_quadrant": ["Q3", "Q2"],
            "period_x": [-0.3, -0.05],
            "period_y": [-0.2, 0.3],
            "cumulative_count": [40, 90],
        }
    )

    df_raw = pd.DataFrame(
        {
            "service": [
                "Service B",
                "Service B",
                "Service B",
                "Service B",
                "Service B",
                "Service B",
            ],
            "date": pd.to_datetime(
                [
                    "2024-01-15",
                    "2024-02-20",
                    "2024-04-10",
                    "2024-04-15",
                    "2024-05-01",
                    "2024-05-10",
                ]
            ),
            "issue_type": [
                "billing",
                "billing",
                "support",
                "support",
                "support",
                "support",
            ],
        }
    )

    analysis = extract_transition_drivers(
        movement_df=movement_data,
        df_raw=df_raw,
        entity_name="Service B",
        quarter_from="2024-Q2",
        quarter_to="2024-Q3",
        entity_col="service",
        timestamp_col="date",
        subcategory_cols=["issue_type"],
        top_n_subcategories=1,
        min_subcategory_delta=2,
    )

    sub_drivers = analysis["subcategory_drivers"]["issue_type"]["top_drivers"]
    assert len(sub_drivers) == 1
    assert sub_drivers[0]["name"] == "support"
    assert sub_drivers[0]["delta"] >= 2

    meta = analysis["meta"]
    assert meta["subcategory_columns_auto_detected"] is False
    assert meta["subcategory_columns_used"] == ["issue_type"]
    assert meta["custom_driver_columns_loaded"] is False


def test_extract_transition_drivers_fallback_detection():
    """Auto-detects reasonable subcategory columns when none provided."""

    movement_data = pd.DataFrame(
        {
            "entity": ["Service C", "Service C"],
            "quarter": ["2024-Q1", "2024-Q2"],
            "period_quadrant": ["Q4", "Q2"],
            "period_x": [-0.4, 0.1],
            "period_y": [-0.2, 0.3],
            "cumulative_count": [30, 65],
        }
    )

    df_raw = pd.DataFrame(
        {
            "service": ["Service C"] * 8,
            "date": pd.date_range(start="2023-10-01", periods=8, freq="15D"),
            "module": [
                "core",
                "core",
                "api",
                "api",
                "api",
                "billing",
                "billing",
                "billing",
            ],
        }
    )

    analysis = extract_transition_drivers(
        movement_df=movement_data,
        df_raw=df_raw,
        entity_name="Service C",
        quarter_from="2024-Q1",
        quarter_to="2024-Q2",
        entity_col="service",
        timestamp_col="date",
    )

    meta = analysis["meta"]
    assert meta["subcategory_columns_auto_detected"] is True
    assert meta["subcategory_columns_used"] == ["module"]
    assert meta["custom_driver_columns_loaded"] is False
    assert "module" in analysis["subcategory_drivers"]
