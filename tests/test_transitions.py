"""Tests for transition detection."""

import pandas as pd
from priorityx.tracking.transitions import classify_transition_risk, extract_transitions


def test_classify_transition_risk_critical():
    """Test critical risk transitions."""
    risk, desc = classify_transition_risk("Q2", "Q1")
    assert risk == "critical"
    assert "critical" in desc.lower()


def test_classify_transition_risk_high():
    """Test high risk transitions."""
    risk, desc = classify_transition_risk("Q3", "Q2")
    assert risk == "high"


def test_classify_transition_risk_low():
    """Test low risk transitions."""
    risk, desc = classify_transition_risk("Q1", "Q4")
    assert risk == "low"


def test_extract_transitions():
    """Test transition extraction from movement data."""
    movement_df = pd.DataFrame({
        "entity": ["A", "A", "A", "B", "B", "B"],
        "quarter": ["2024-Q1", "2024-Q2", "2024-Q3"] * 2,
        "period_quadrant": ["Q3", "Q2", "Q1", "Q4", "Q4", "Q4"],
        "global_quadrant": ["Q2", "Q2", "Q2", "Q4", "Q4", "Q4"],
        "x_delta": [0.1, 0.2, 0.3, 0.05, 0.05, 0.05],
        "y_delta": [0.1, 0.2, 0.3, 0.02, 0.02, 0.02],
    })

    transitions = extract_transitions(movement_df)

    assert len(transitions) > 0
    assert "entity" in transitions.columns
    assert "risk_level" in transitions.columns


def test_extract_transitions_within_quadrant():
    """Test within-quadrant dramatic changes."""
    movement_df = pd.DataFrame({
        "entity": ["A", "A"],
        "quarter": ["2024-Q1", "2024-Q2"],
        "period_quadrant": ["Q2", "Q2"],
        "global_quadrant": ["Q2", "Q2"],
        "x_delta": [None, 0.5],
        "y_delta": [None, 1.5],  # dramatic acceleration
    })

    transitions = extract_transitions(movement_df)

    assert len(transitions) > 0
    assert transitions.iloc[0]["risk_level"] == "critical"
