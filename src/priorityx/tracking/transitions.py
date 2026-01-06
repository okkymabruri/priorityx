"""Transition detection from movement tracking data."""

from typing import Iterable, Tuple

import pandas as pd


def classify_transition_risk(from_quadrant: str, to_quadrant: str) -> Tuple[str, str]:
    """
    Classify risk level and type of a quadrant transition.

    Maps quadrant-to-quadrant transitions to risk levels based on
    trajectory through priority space.

    Args:
        from_quadrant: Starting quadrant (Q1-Q4)
        to_quadrant: Ending quadrant (Q1-Q4)

    Returns:
        Tuple of (risk_level, transition_description)
        - risk_level: "critical", "high", "medium", "low", or "stable"
        - transition_description: Human-readable description

    Risk Classification:
        **Critical**: Transitions TO Q1 (Critical)
        - Q2→Q1: Emerging issue became critical
        - Q3→Q1: Low priority escalated to critical
        - Q4→Q1: Persistent issue became critical

        **High**: Transitions TO Q2 (Investigate)
        - Q3→Q2: Low priority becoming emerging threat
        - Q4→Q2: Persistent issue showing growth

        **Medium**: Other risk-increasing transitions
        - Q4→Q3: Persistent issue losing volume (watch)

        **Low**: Risk-decreasing transitions
        - Q1→Q2: Critical issue volume decreasing
        - Q1→Q4: Critical issue growth slowing
        - Q2→Q3: Emerging threat growth slowing

        **Stable**: All other transitions

    Examples:
        >>> classify_transition_risk("Q2", "Q1")
        ('critical', 'Emerging issue became critical')

        >>> classify_transition_risk("Q3", "Q2")
        ('high', 'Low priority becoming emerging threat')

        >>> classify_transition_risk("Q1", "Q4")
        ('low', 'Critical issue growth slowing')
    """
    # critical transitions (moving to Q1)
    critical_transitions = {
        ("Q2", "Q1"): "Emerging issue became critical",
        ("Q3", "Q1"): "Low priority escalated to critical",
        ("Q4", "Q1"): "Persistent issue became critical",
    }

    # high risk transitions (moving to Q2)
    high_risk_transitions = {
        ("Q3", "Q2"): "Low priority becoming emerging threat",
        ("Q4", "Q2"): "Persistent issue showing growth",
    }

    # medium risk transitions
    medium_risk_transitions = {("Q4", "Q3"): "Persistent issue losing volume (watch)"}

    # low risk transitions (improvements)
    low_risk_transitions = {
        ("Q1", "Q2"): "Critical issue volume decreasing",
        ("Q1", "Q4"): "Critical issue growth slowing",
        ("Q2", "Q3"): "Emerging threat growth slowing",
    }

    transition_key = (from_quadrant, to_quadrant)

    if transition_key in critical_transitions:
        return "critical", critical_transitions[transition_key]
    elif transition_key in high_risk_transitions:
        return "high", high_risk_transitions[transition_key]
    elif transition_key in medium_risk_transitions:
        return "medium", medium_risk_transitions[transition_key]
    elif transition_key in low_risk_transitions:
        return "low", low_risk_transitions[transition_key]
    else:
        return "stable", f"Transition from {from_quadrant} to {to_quadrant}"


def extract_transitions(
    movement_df: pd.DataFrame,
    focus_risk_increasing: bool = True,
) -> pd.DataFrame:
    """
    Extract quadrant transitions from cumulative movement tracking data.

    Detects two types of transitions:
    1. Quadrant-to-quadrant transitions (Q3→Q2, Q2→Q1, etc.)
    2. Within-quadrant dramatic changes (velocity thresholds)

    Args:
        movement_df: DataFrame from track_cumulative_movement(). Expected
                    to contain the canonical period column (``quarter``)
                    whose labels may be quarterly ("YYYY-QN") or monthly
                    ("YYYY-MM"), plus: entity, period_quadrant,
                    global_quadrant, period_x, period_y, x_delta, y_delta.
        focus_risk_increasing: Only return risk-increasing transitions (default: True)
                              If False, includes all transitions including improvements

    Returns:
        DataFrame with columns:
        - entity: Entity name
        - transition_quarter: When transition occurred
        - from_quadrant: Previous period quadrant
        - to_quadrant: New period quadrant (with * for within-quadrant)
        - risk_level: "critical", "high", "medium", "low", or "stable"
        - volume_change: X-axis delta
        - growth_change: Y-axis delta
        - transition_type: Human-readable description
        - global_quadrant: Stable baseline quadrant (for reference)

    Examples:
        >>> transitions = extract_transitions(movement_df)
        >>> critical = transitions[transitions['risk_level'] == 'critical']

        >>> # include all transitions (not just risk-increasing)
        >>> all_trans = extract_transitions(movement_df, focus_risk_increasing=False)
    """
    transitions = []

    period_col = "quarter"

    # group by entity and sort by period
    for entity, entity_data in movement_df.groupby("entity"):
        entity_data = entity_data.sort_values(period_col)

        # get global quadrant (stable across all periods)
        global_quad = entity_data.iloc[0]["global_quadrant"]

        # detect period quadrant transitions
        for i in range(len(entity_data) - 1):
            curr_row = entity_data.iloc[i]
            next_row = entity_data.iloc[i + 1]

            # check if period quadrant changed
            if curr_row["period_quadrant"] != next_row["period_quadrant"]:
                from_quad = curr_row["period_quadrant"]
                to_quad = next_row["period_quadrant"]

                # classify risk based on transition pattern
                risk_level, transition_type = classify_transition_risk(
                    from_quad, to_quad
                )

                # filter if focusing on risk-increasing only
                if focus_risk_increasing and risk_level in ["low", "stable"]:
                    continue

                transitions.append(
                    {
                        "entity": entity,
                        "transition_quarter": next_row[period_col],
                        "from_quadrant": from_quad,
                        "to_quadrant": to_quad,
                        "risk_level": risk_level,
                        "volume_change": next_row["x_delta"],
                        "growth_change": next_row["y_delta"],
                        "transition_type": transition_type,
                        "global_quadrant": global_quad,
                    }
                )

            # detect dramatic changes WITHIN same period quadrant
            elif curr_row["period_quadrant"] == next_row["period_quadrant"]:
                growth_change = next_row["y_delta"]
                volume_change = next_row["x_delta"]

                # flag dramatic acceleration (Y-axis surge > 1.0)
                if growth_change > 1.0:
                    transitions.append(
                        {
                            "entity": entity,
                            "transition_quarter": next_row[period_col],
                            "from_quadrant": curr_row["period_quadrant"],
                            "to_quadrant": f"{next_row['period_quadrant']}*Y",  # *Y = growth spike
                            "risk_level": "critical",
                            "volume_change": volume_change,
                            "growth_change": growth_change,
                            "transition_type": f"Dramatic acceleration within {next_row['period_quadrant']} (+{growth_change:.1f} growth)",
                            "global_quadrant": global_quad,
                        }
                    )

                # flag dramatic volume increase (X-axis surge > 1.0)
                elif volume_change > 1.0:
                    transitions.append(
                        {
                            "entity": entity,
                            "transition_quarter": next_row["quarter"],
                            "from_quadrant": curr_row["period_quadrant"],
                            "to_quadrant": f"{next_row['period_quadrant']}*X",  # *X = volume spike
                            "risk_level": "high",
                            "volume_change": volume_change,
                            "growth_change": growth_change,
                            "transition_type": f"Major volume surge within {next_row['period_quadrant']} (+{volume_change:.1f} volume)",
                            "global_quadrant": global_quad,
                        }
                    )

    return pd.DataFrame(transitions)


def filter_transitions(
    df: pd.DataFrame,
    *,
    window: Iterable[str],
    exclude_quadrant_prefixes: Iterable[str] = ("Q4",),
) -> pd.DataFrame:
    """Filter transitions to a time window and drop moves involving excluded quadrants."""
    if df.empty:
        return df

    df = df.copy()
    df["transition_quarter"] = df["transition_quarter"].astype(str)
    df["from_quadrant"] = df["from_quadrant"].astype(str)
    df["to_quadrant"] = df["to_quadrant"].astype(str)

    filtered = df[df["transition_quarter"].isin(window)].copy()

    if exclude_quadrant_prefixes:
        mask = False
        for prefix in exclude_quadrant_prefixes:
            mask |= filtered["from_quadrant"].str.startswith(prefix)
            mask |= filtered["to_quadrant"].str.startswith(prefix)
        filtered = filtered[~mask]

    return filtered.reset_index(drop=True)


def classify_priority(
    from_quadrant: str,
    to_quadrant: str,
    x: float,
    y: float,
    x_delta: float,
    y_delta: float,
    complaints_delta: int,
    percent_change: float,
) -> tuple:
    """
    Classify supervisory priority (4-tier: Crisis/Investigate/Monitor/Low).

    Uses movement dynamics (velocity, direction, magnitude) to determine
    action urgency beyond simple quadrant transitions.

    Args:
        from_quadrant: Starting quadrant (Q1-Q4)
        to_quadrant: Ending quadrant (Q1-Q4)
        x: Current X-axis position (volume)
        y: Current Y-axis position (growth rate)
        x_delta: Change in X-axis (volume change)
        y_delta: Change in Y-axis (growth rate change)
        complaints_delta: Absolute change in complaints
        percent_change: Percentage change in complaints

    Returns:
        Tuple of (priority, reason, spike_axis) where:
        - priority: 1=Crisis, 2=Investigate, 3=Monitor, 4=Low
        - reason: Explanation string
        - spike_axis: 'Y', 'X', 'XY', or None

    Examples:
        >>> # dramatic acceleration
        >>> classify_priority("Q2", "Q1", 1.2, 0.8, 0.3, 0.5, 150, 200)
        (1, "Crisis: Extreme movement (ΔX=0.30, ΔY=0.50)", 'Y')

        >>> # moderate movement
        >>> classify_priority("Q3", "Q2", 0.5, 0.4, 0.1, 0.2, 30, 50)
        (2, "Velocity trigger (ΔX=0.10, ΔY=0.20)", None)
    """
    # check if borderline (within ±0.1 of threshold)
    is_borderline = abs(x) <= 0.1 or abs(y) <= 0.1

    # check if moving to Q1 (critical quadrant)
    to_critical = to_quadrant == "Q1"

    # determine spike axis for Crisis level (0.40 ≈ 2.74σ, aligns with 3-sigma rule)
    y_spike = abs(y_delta) > 0.40
    x_spike = abs(x_delta) > 0.40
    explosion = percent_change > 500 and complaints_delta > 50

    # Priority 1: Crisis
    if y_spike or x_spike or explosion:
        if y_spike and x_spike:
            spike_axis = "XY"
        elif y_spike:
            spike_axis = "Y"
        elif x_spike:
            spike_axis = "X"
        else:
            spike_axis = "Y"  # default for explosions

        return (
            1,
            f"Crisis: Extreme movement (ΔX={x_delta:.2f}, ΔY={y_delta:.2f})",
            spike_axis,
        )

    # Priority 2: Investigate
    if abs(x_delta) > 0.15 or abs(y_delta) > 0.15:
        return 2, f"Velocity trigger (ΔX={x_delta:.2f}, ΔY={y_delta:.2f})", None

    if to_critical and not is_borderline:
        return 2, "Critical destination, clear (→Q1)", None

    if percent_change > 100 and complaints_delta >= 5:
        return 2, f"Growth shock (+{complaints_delta}, {percent_change:.0f}%)", None

    # Priority 3: Monitor
    if is_borderline or to_critical:
        return 3, "Borderline/threshold crossing", None

    # Priority 4: Low (improvements, stable)
    return 4, "Routine/improving", None
