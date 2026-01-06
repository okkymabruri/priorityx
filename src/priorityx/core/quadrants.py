"""Quadrant classification for priority matrices."""


def classify_quadrant(
    intercept: float, slope: float, count: float = None, min_q1_count: int = 50
) -> str:
    """
    Classify entity into priority quadrant based on coordinates.

    Quadrant is determined purely by position (intercept/slope signs).
    Count thresholds should be applied at filtering/visualization time,
    not during classification.

    Args:
        intercept: Random intercept (volume indicator)
        slope: Random slope (growth indicator)
        count: (Deprecated) Retained for API compatibility, not used
        min_q1_count: (Deprecated) Retained for API compatibility, not used

    Returns:
        Quadrant code: Q1 (Critical), Q2 (Investigate), Q3 (Monitor), Q4 (Low)
    """
    if intercept > 0 and slope > 0:
        return "Q1"  # crisis (high volume, high growth)
    elif intercept <= 0 and slope > 0:
        return "Q2"  # investigate (low volume, high growth)
    elif intercept <= 0 and slope <= 0:
        return "Q3"  # monitor (low volume, low growth)
    else:
        return "Q4"  # low priority (high volume, low growth)


def get_quadrant_label(
    quadrant_code: str, x_label: str = "Volume", y_label: str = "Growth"
) -> str:
    """Get human-readable label for quadrant code.

    Args:
        quadrant_code: Q1-Q4
        x_label: Label for X-axis metric (e.g., "Volume", "Market Share", "Bugs")
        y_label: Label for Y-axis metric (e.g., "Growth", "Incident Rate")
    """
    labels = {
        "Q1": f"Q1 (High {x_label}, High {y_label})",
        "Q2": f"Q2 (Low {x_label}, High {y_label})",
        "Q3": f"Q3 (Low {x_label}, Low {y_label})",
        "Q4": f"Q4 (High {x_label}, Low {y_label})",
    }
    return labels.get(quadrant_code, quadrant_code)


def get_risk_level(quadrant_code: str) -> str:
    """Map quadrant to risk level."""
    risk_map = {
        "Q1": "Critical",
        "Q2": "Investigate",
        "Q3": "Monitor",
        "Q4": "Low",
    }
    return risk_map.get(quadrant_code, "Unknown")
