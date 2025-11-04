"""Tests for quadrant classification."""

from priorityx.core.quadrants import classify_quadrant, get_quadrant_label, get_risk_level


def test_classify_quadrant_q1():
    """Test Q1 classification: high volume, high growth."""
    assert classify_quadrant(1.5, 0.8, count=100) == "Q1"

def test_classify_quadrant_q1_threshold():
    """Test Q1 threshold: insufficient count reclassified to Q2."""
    assert classify_quadrant(1.5, 0.8, count=20) == "Q2"

def test_classify_quadrant_q2():
    """Test Q2 classification: low volume, high growth."""
    assert classify_quadrant(-0.5, 0.6) == "Q2"

def test_classify_quadrant_q3():
    """Test Q3 classification: low volume, low growth."""
    assert classify_quadrant(-0.5, -0.3) == "Q3"

def test_classify_quadrant_q4():
    """Test Q4 classification: high volume, low growth."""
    assert classify_quadrant(1.2, -0.2) == "Q4"


def test_get_quadrant_label():
    """Test quadrant label retrieval."""
    assert "High Volume, High Growth" in get_quadrant_label("Q1")
    assert "Low Volume, High Growth" in get_quadrant_label("Q2")
    assert "Low Volume, Low Growth" in get_quadrant_label("Q3")
    assert "High Volume, Low Growth" in get_quadrant_label("Q4")


def test_get_risk_level():
    """Test risk level mapping."""
    assert get_risk_level("Q1") == "Critical"
    assert get_risk_level("Q2") == "Investigate"
    assert get_risk_level("Q3") == "Monitor"
    assert get_risk_level("Q4") == "Low"
