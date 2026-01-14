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


def test_extract_transition_drivers_numeric_cols():
    """Test numeric column binning and driver extraction."""
    import numpy as np

    movement_data = pd.DataFrame(
        {
            "entity": ["Product X", "Product X"],
            "quarter": ["2024-Q2", "2024-Q3"],
            "period_quadrant": ["Q3", "Q1"],
            "period_x": [-0.1, 0.3],
            "period_y": [-0.1, 0.4],
            "cumulative_count": [100, 200],
        }
    )

    # create raw data with amount column
    np.random.seed(42)
    n_from = 30
    n_to = 70

    df_raw = pd.DataFrame(
        {
            "product": ["Product X"] * (n_from + n_to),
            "date": (
                list(pd.date_range("2024-01-15", periods=n_from, freq="D"))
                + list(pd.date_range("2024-04-10", periods=n_to, freq="D"))
            ),
            "amount": (
                list(np.random.uniform(0, 1e6, n_from))  # mostly low amounts in Q2
                + list(np.random.uniform(5e6, 10e6, n_to))  # mostly high amounts in Q3
            ),
            "region": (
                ["Jakarta"] * 15 + ["Surabaya"] * 15
                + ["Jakarta"] * 50 + ["Bandung"] * 20
            ),
        }
    )

    analysis = extract_transition_drivers(
        movement_df=movement_data,
        df_raw=df_raw,
        entity_name="Product X",
        period_from="2024-Q2",
        period_to="2024-Q3",
        entity_col="product",
        timestamp_col="date",
        subcategory_cols=["region"],
        numeric_cols={
            "amount": [0, 1e6, 5e6, 10e6],  # explicit bins
        },
        top_n=3,
    )

    # verify structure
    assert "subcategory_drivers" in analysis
    assert "numeric_drivers" in analysis
    assert "amount" in analysis["numeric_drivers"]

    # verify numeric drivers have expected structure
    amount_drivers = analysis["numeric_drivers"]["amount"]
    assert "top_drivers" in amount_drivers
    assert "top_n_explain_pct" in amount_drivers
    assert "bin_edges" in amount_drivers

    # verify bin edges match input
    assert amount_drivers["bin_edges"] == [0, 1e6, 5e6, 10e6]

    # verify top drivers have required fields
    for driver in amount_drivers["top_drivers"]:
        assert "bin" in driver
        assert "count_from" in driver
        assert "count_to" in driver
        assert "delta" in driver
        assert "percent_of_change" in driver

    # verify meta includes numeric columns
    assert "numeric_columns_used" in analysis["meta"]
    assert "amount" in analysis["meta"]["numeric_columns_used"]


def test_extract_transition_drivers_numeric_quantile_bins():
    """Test numeric column with quantile bins (integer spec)."""
    import numpy as np

    movement_data = pd.DataFrame(
        {
            "entity": ["Service Y", "Service Y"],
            "quarter": ["2024-Q2", "2024-Q3"],
            "period_quadrant": ["Q3", "Q2"],
            "period_x": [-0.2, 0.0],
            "period_y": [-0.1, 0.2],
            "cumulative_count": [50, 90],
        }
    )

    np.random.seed(123)
    n_from = 20
    n_to = 40

    df_raw = pd.DataFrame(
        {
            "service": ["Service Y"] * (n_from + n_to),
            "date": (
                list(pd.date_range("2024-01-15", periods=n_from, freq="D"))
                + list(pd.date_range("2024-04-10", periods=n_to, freq="D"))
            ),
            "resolution_days": (
                list(np.random.uniform(1, 10, n_from))
                + list(np.random.uniform(5, 30, n_to))
            ),
        }
    )

    analysis = extract_transition_drivers(
        movement_df=movement_data,
        df_raw=df_raw,
        entity_name="Service Y",
        period_from="2024-Q2",
        period_to="2024-Q3",
        entity_col="service",
        timestamp_col="date",
        numeric_cols={
            "resolution_days": 4,  # 4 quantile bins
        },
    )

    assert "numeric_drivers" in analysis
    assert "resolution_days" in analysis["numeric_drivers"]

    res_drivers = analysis["numeric_drivers"]["resolution_days"]
    assert len(res_drivers["bin_edges"]) == 5  # 4 bins = 5 edges


def test_extract_transition_drivers_backwards_compat():
    """Test that old parameter names still work."""
    movement_data = pd.DataFrame(
        {
            "entity": ["Service Z", "Service Z"],
            "quarter": ["2024-Q2", "2024-Q3"],
            "period_quadrant": ["Q3", "Q2"],
            "period_x": [-0.2, -0.1],
            "period_y": [-0.1, 0.2],
            "cumulative_count": [50, 80],
        }
    )

    df_raw = pd.DataFrame(
        {
            "service": ["Service Z"] * 10,
            "date": pd.date_range("2024-01-01", periods=10, freq="20D"),
            "category": ["A"] * 5 + ["B"] * 5,
        }
    )

    # use old parameter names
    analysis = extract_transition_drivers(
        movement_df=movement_data,
        df_raw=df_raw,
        entity_name="Service Z",
        quarter_from="2024-Q2",  # old name
        quarter_to="2024-Q3",    # old name
        entity_col="service",
        timestamp_col="date",
        subcategory_cols=["category"],
        top_n_subcategories=2,   # old name
        min_subcategory_delta=1, # old name
    )

    assert "transition" in analysis
    assert analysis["transition"]["from_quarter"] == "2024-Q2"
    assert analysis["transition"]["to_quarter"] == "2024-Q3"
