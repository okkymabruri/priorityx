"""Tests for plot_priority_matrix axis selection hooks.

These tests are light smoke tests that ensure the function accepts
custom x/y columns without raising and returns a Matplotlib figure.
"""

import pandas as pd

import priorityx as px


def _make_results_df() -> pd.DataFrame:
    # current version: use x_score/y_score column names
    return pd.DataFrame(
        {
            "entity": ["A", "B"],
            "x_score": [0.1, 0.2],
            "y_score": [0.01, 0.02],
            "alt_x": [1.0, 2.0],
            "alt_y": [10.0, 20.0],
            "quadrant": ["Q1", "Q2"],
            "count": [100, 200],
        }
    )


def test_plot_priority_matrix_default_axes():
    df = _make_results_df()
    fig = px.plot_priority_matrix(df, entity_name="Test")
    assert fig is not None


def test_plot_priority_matrix_custom_axes_and_bubble():
    df = _make_results_df()
    df["bubble"] = [5, 10]

    fig = px.plot_priority_matrix(
        df,
        entity_name="Test",
        x_col="alt_x",
        y_col="alt_y",
        bubble_col="bubble",
        x_label="Alt X",
        y_label="Alt Y",
    )

    assert fig is not None
