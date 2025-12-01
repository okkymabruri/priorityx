"""Transition driver analysis for identifying root causes of quadrant transitions."""

import pandas as pd
from typing import Dict, List, Optional, Tuple, Set
import re
from datetime import datetime
from pathlib import Path

DEFAULT_DRIVER_COLUMNS: Tuple[str, ...] = (
    # products
    "product",
    "type",
    # topics / issues
    "topic",
    "issue_type",
    # severity / categories
    "severity",
    "category",
)

MAX_AUTO_SUBCATEGORY_UNIQUE = 25

PROJECT_ROOT = Path(__file__).resolve().parents[3]
CUSTOM_DRIVER_COLUMNS_FILE = PROJECT_ROOT / "tmp" / "driver_columns.txt"


def _load_custom_driver_columns() -> List[str]:
    """Load additional driver column aliases from tmp/driver_columns.txt (one per line)."""

    try:
        contents = CUSTOM_DRIVER_COLUMNS_FILE.read_text(encoding="utf-8")
    except FileNotFoundError:
        return []
    except OSError:
        return []

    columns: List[str] = []
    for line in contents.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        columns.append(stripped)
    return columns


def _detect_subcategory_columns(
    df: pd.DataFrame,
    requested: Optional[List[str]],
    entity_col: str,
    timestamp_col: str,
    custom_aliases: Optional[List[str]] = None,
    max_unique: int = MAX_AUTO_SUBCATEGORY_UNIQUE,
) -> Tuple[List[str], bool]:
    """Determine which columns to use for driver aggregation."""

    exclude = {entity_col.lower(), timestamp_col.lower()}

    if requested:
        sanitized = [col for col in requested if col in df.columns]
        if sanitized:
            return sanitized, False
        # fall through to auto-detect if provided columns missing

    detected: List[str] = []
    detected_lower: Set[str] = set()
    lower_map = {col.lower(): col for col in df.columns if col.lower() not in exclude}

    alias_candidates = list(DEFAULT_DRIVER_COLUMNS)
    if custom_aliases:
        alias_candidates.extend(custom_aliases)

    for alias in alias_candidates:
        match = lower_map.get(alias.lower())
        if match and match.lower() not in detected_lower:
            detected.append(match)
            detected_lower.add(match.lower())

    if not detected:
        for col in df.columns:
            col_lower = col.lower()
            if col_lower in exclude or col_lower in detected_lower:
                continue

            series = df[col]
            if pd.api.types.is_object_dtype(
                series
            ) or pd.api.types.is_categorical_dtype(series):
                unique_vals = series.nunique(dropna=True)
                if 1 < unique_vals <= max_unique:
                    detected.append(col)
                    detected_lower.add(col_lower)
            if len(detected) >= 2:
                break

    return detected, True


def _get_quadrant_label(quadrant_code: str) -> str:
    """Return human-readable label for a quadrant code."""
    labels = {
        "Q1": "Q1 (High Volume, High Growth)",
        "Q2": "Q2 (Low Volume, High Growth)",
        "Q3": "Q3 (Low Volume, Low Growth)",
        "Q4": "Q4 (High Volume, Low Growth)",
    }
    return labels.get(quadrant_code, quadrant_code)


def _get_risk_level(quadrant_code: str) -> str:
    """Map quadrant code to supervisory risk level."""
    risk_map = {
        "Q1": "Critical",
        "Q2": "Emerging",
        "Q3": "Low Priority",
        "Q4": "Persistent",
    }
    return risk_map.get(quadrant_code, "Unknown")


def _classify_transition_concern(from_q: str, to_q: str) -> bool:
    """Return True when transition represents increasing supervisory concern."""
    if to_q in {"Q1", "Q2"}:
        return True
    risk_order = {"Q3": 1, "Q4": 2, "Q2": 3, "Q1": 4}
    return risk_order.get(to_q, 0) > risk_order.get(from_q, 0)


def _calculate_quarter_dates(quarter_str: str) -> Tuple[str, str]:
    """
    Convert quarter string to start/end dates.

    Args:
        quarter_str: Quarter in format "YYYY-QN" (e.g., "2024-Q3")

    Returns:
        Tuple of (start_date, end_date) as ISO strings

    Examples:
        >>> _calculate_quarter_dates("2024-Q3")
        ('2024-04-01', '2024-07-01')
    """
    match = re.match(r"(\d{4})-Q(\d)", quarter_str)
    if not match:
        raise ValueError(
            f"Invalid quarter format: {quarter_str}. Use 'YYYY-QN' (e.g., '2024-Q3')"
        )

    year = int(match.group(1))
    quarter = int(match.group(2))

    # quarter start dates
    quarter_starts = {
        1: (year - 1, 10, 1),  # Q1 starts Oct 1 of prev year
        2: (year, 1, 1),  # Q2 starts Jan 1
        3: (year, 4, 1),  # Q3 starts Apr 1
        4: (year, 7, 1),  # Q4 starts Jul 1
    }

    if quarter not in quarter_starts:
        raise ValueError(f"Quarter must be 1-4, got: {quarter}")

    y, m, d = quarter_starts[quarter]
    start_date = datetime(y, m, d)

    # calculate next quarter start (exact end date)
    next_quarter = quarter + 1 if quarter < 4 else 1
    next_year = year if quarter < 4 else year + 1
    ey, em, ed = quarter_starts[next_quarter]
    if next_quarter == 1:
        ey = next_year
    end_date = datetime(ey, em, ed)

    return start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d")


def classify_priority(
    from_quadrant: str,
    to_quadrant: str,
    x: float,
    y: float,
    x_delta: float,
    y_delta: float,
    count_delta: int,
    percent_change: float,
) -> Tuple[int, str, Optional[str]]:
    """
    Classify supervisory priority based on transition characteristics.

    4-tier system:
    - Priority 1 (Critical): Extreme movement or explosion
    - Priority 2 (Investigate): Significant velocity or growth shock
    - Priority 3 (Monitor): Borderline or threshold crossing
    - Priority 4 (Low): Routine or improving

    Args:
        from_quadrant: Starting quadrant code
        to_quadrant: Ending quadrant code
        x: Current X-axis position
        y: Current Y-axis position
        x_delta: X-axis change
        y_delta: Y-axis change
        count_delta: Absolute count change
        percent_change: Percent change in count

    Returns:
        Tuple of (priority, reason, spike_axis) where:
        - priority: 1=Critical, 2=Investigate, 3=Monitor, 4=Low
        - reason: Explanation string
        - spike_axis: 'Y', 'X', 'XY', or None

    Examples:
        >>> classify_priority("Q3", "Q1", 0.5, 0.6, 0.5, 0.5, 100, 200)
        (1, 'Critical: Extreme movement (ΔX=0.50, ΔY=0.50)', 'XY')
    """
    is_borderline = abs(x) <= 0.1 or abs(y) <= 0.1
    to_critical = to_quadrant == "Q1"

    # crisis triggers (0.4 = 2.74 SD, aligns with 3-sigma rule)
    y_spike = abs(y_delta) > 0.4
    x_spike = abs(x_delta) > 0.4
    explosion = percent_change > 500 and count_delta > 50

    # priority 1: critical
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
            f"Critical: Extreme movement (dX={x_delta:.2f}, dY={y_delta:.2f})",
            spike_axis,
        )

    # priority 2: investigate
    if abs(x_delta) > 0.15 or abs(y_delta) > 0.15:
        return 2, f"Velocity trigger (dX={x_delta:.2f}, dY={y_delta:.2f})", None

    if to_critical and not is_borderline:
        return 2, "Critical destination, clear (to Q1)", None

    if percent_change > 100 and count_delta >= 5:
        return 2, f"Growth shock (+{count_delta}, {percent_change:.0f}%)", None

    # priority 3: monitor
    if is_borderline or to_critical:
        return 3, "Borderline/threshold crossing", None

    # priority 4: low
    return 4, "Routine/improving", None


def extract_transition_drivers(
    movement_df: pd.DataFrame,
    df_raw: pd.DataFrame,
    entity_name: str,
    quarter_from: str,
    quarter_to: str,
    entity_col: str = "entity",
    timestamp_col: str = "date",
    subcategory_cols: Optional[List[str]] = None,
    top_n_subcategories: int = 5,
    min_subcategory_delta: int = 2,
) -> Dict:
    """
    Extract key drivers of a quadrant transition.

    Analyzes what drove a specific entity to transition between quadrants,
    including volume changes, growth changes, and contributing sub-categories.

    Args:
        movement_df: Output from track_cumulative_movement(). Expected to
            contain the canonical period column ("quarter") whose labels
            may be quarterly ("YYYY-QN") or monthly ("YYYY-MM").
        df_raw: Raw event data (pandas DataFrame)
        entity_name: Entity to analyze
        quarter_from: Starting period label (e.g., "2024-Q2" or "2024-03")
        quarter_to: Ending period label (e.g., "2024-Q3" or "2024-04")
        entity_col: Entity column name in df_raw
        timestamp_col: Timestamp column name in df_raw
        subcategory_cols: Optional list of subcategory columns to analyze
        subcategory_cols: Optional list of subcategory columns to analyze, automatically detected if omitted

    Returns:
        Dictionary with structure:
        {
            "transition": {...},           # Overview
            "magnitude": {...},            # Volume/growth changes
            "subcategory_drivers": {...},  # Drivers by subcategory (if available)
            "priority": {...},             # Priority classification
            "meta": {...},                 # Diagnostic metadata
        }

    Examples:
        >>> # Basic analysis
        >>> analysis = extract_transition_drivers(
        ...     movement_df, df, "Service A", "2024-Q2", "2024-Q3",
        ...     entity_col="service", timestamp_col="date"
        ... )

        >>> # With subcategories
        >>> analysis = extract_transition_drivers(
        ...     movement_df, df, "FSP X", "2024-Q2", "2024-Q3",
        ...     subcategory_cols=["topic", "product"]
        ... )
    """
    df_raw = df_raw.copy()
    df_raw[timestamp_col] = pd.to_datetime(df_raw[timestamp_col])

    # get transition data from movement_df
    period_col = "quarter"
    entity_data = movement_df[movement_df["entity"] == entity_name]

    if len(entity_data) == 0:
        raise ValueError(f"Entity '{entity_name}' not found in movement data")

    from_data = entity_data[entity_data[period_col] == quarter_from]
    to_data = entity_data[entity_data[period_col] == quarter_to]

    if len(from_data) == 0:
        raise ValueError(f"Quarter '{quarter_from}' not found for '{entity_name}'")
    if len(to_data) == 0:
        raise ValueError(f"Quarter '{quarter_to}' not found for '{entity_name}'")

    from_row = from_data.iloc[0]
    to_row = to_data.iloc[0]

    from_quadrant = from_row["period_quadrant"]
    to_quadrant = to_row["period_quadrant"]

    # period-specific complaints (per quarter) for hybrid analysis
    from_start, from_end = _calculate_quarter_dates(quarter_from)
    to_start, to_end = _calculate_quarter_dates(quarter_to)

    entity_complaints = df_raw[df_raw[entity_col] == entity_name]

    from_period_data = entity_complaints[
        (entity_complaints[timestamp_col] >= pd.Timestamp(from_start))
        & (entity_complaints[timestamp_col] < pd.Timestamp(from_end))
    ]

    to_period_data = entity_complaints[
        (entity_complaints[timestamp_col] >= pd.Timestamp(to_start))
        & (entity_complaints[timestamp_col] < pd.Timestamp(to_end))
    ]

    from_period_count = len(from_period_data)
    to_period_count = len(to_period_data)
    period_increase = to_period_count - from_period_count
    weeks_per_quarter = 13

    # transition overview
    transition_overview = {
        "entity": entity_name,
        "from_quarter": quarter_from,
        "to_quarter": quarter_to,
        "from_quadrant": from_quadrant,
        "to_quadrant": to_quadrant,
        "quadrant_changed": from_quadrant != to_quadrant,
        "from_quadrant_label": _get_quadrant_label(from_quadrant),
        "to_quadrant_label": _get_quadrant_label(to_quadrant),
        "risk_level_change": f"{_get_risk_level(from_quadrant)} → {_get_risk_level(to_quadrant)}",
        "is_concerning": _classify_transition_concern(from_quadrant, to_quadrant),
    }

    # magnitude metrics
    if "cumulative_count" in from_row.index:
        count_col_name = "cumulative_count"
    else:
        count_col_name = None

    if count_col_name:
        count_from = int(from_row[count_col_name])
        count_to = int(to_row[count_col_name])
        absolute_delta = count_to - count_from
        percent_change = (absolute_delta / count_from * 100) if count_from > 0 else 0
    else:
        count_from = 0
        count_to = 0
        absolute_delta = 0
        percent_change = 0

    magnitude_metrics = {
        "volume_change": {
            "count_from": count_from,
            "count_to": count_to,
            "absolute_delta": absolute_delta,
            "percent_change": round(percent_change, 1),
            "x_from": round(from_row["period_x"], 2),
            "x_to": round(to_row["period_x"], 2),
            "x_delta": round(to_row["period_x"] - from_row["period_x"], 2),
        },
        "growth_change": {
            "y_from": round(from_row["period_y"], 2),
            "y_to": round(to_row["period_y"], 2),
            "y_delta": round(to_row["period_y"] - from_row["period_y"], 2),
            "weekly_avg_from": round(from_period_count / weeks_per_quarter, 1),
            "weekly_avg_to": round(to_period_count / weeks_per_quarter, 1),
        },
        "period_counts": {
            "count_from": from_period_count,
            "count_to": to_period_count,
            "absolute_delta": period_increase,
        },
    }

    # priority classification
    priority, reason, spike_axis = classify_priority(
        from_quadrant=from_quadrant,
        to_quadrant=to_quadrant,
        x=to_row["period_x"],
        y=to_row["period_y"],
        x_delta=to_row["period_x"] - from_row["period_x"],
        y_delta=to_row["period_y"] - from_row["period_y"],
        count_delta=absolute_delta,
        percent_change=percent_change,
    )

    priority_classification = {
        "priority": priority,
        "priority_name": {1: "Critical", 2: "Investigate", 3: "Monitor", 4: "Low"}[
            priority
        ],
        "trigger_reason": reason,
        "spike_axis": spike_axis,
        "is_borderline": abs(to_row["period_x"]) <= 0.1
        or abs(to_row["period_y"]) <= 0.1,
    }

    # spike driver summary (ties to spike indicators / priority triggers)
    spike_drivers = _summarize_spike_drivers(priority_classification, magnitude_metrics)

    # initialize result
    result = {
        "transition": transition_overview,
        "magnitude": magnitude_metrics,
        "priority": priority_classification,
        "spike_drivers": spike_drivers,
    }

    custom_driver_aliases = _load_custom_driver_columns()
    effective_subcats, auto_detected_subcats = _detect_subcategory_columns(
        df_raw,
        subcategory_cols,
        entity_col,
        timestamp_col,
        custom_aliases=custom_driver_aliases,
    )

    if effective_subcats:
        result["subcategory_drivers"] = _analyze_subcategory_drivers(
            from_period_data,
            to_period_data,
            effective_subcats,
            absolute_delta,
            top_n=top_n_subcategories,
            min_delta=min_subcategory_delta,
        )

    result["meta"] = {
        "subcategory_columns_used": effective_subcats,
        "subcategory_columns_auto_detected": auto_detected_subcats,
        "custom_driver_columns_loaded": bool(custom_driver_aliases),
    }

    return result


def _summarize_spike_drivers(priority_info: Dict, magnitude: Dict) -> Dict:
    """Create a compact summary describing what triggered spike flags."""

    summary_notes: List[str] = []
    spike_axis = priority_info.get("spike_axis")
    volume = magnitude.get("volume_change", {})
    growth = magnitude.get("growth_change", {})

    y_delta = growth.get("y_delta")
    x_delta = volume.get("x_delta")

    if spike_axis in {"Y", "XY"} and y_delta is not None:
        summary_notes.append(f"Y-axis spike (ΔY={y_delta:+.2f})")
    if spike_axis in {"X", "XY"} and x_delta is not None:
        summary_notes.append(f"X-axis spike (ΔX={x_delta:+.2f})")

    percent_change = volume.get("percent_change", 0)
    absolute_delta = volume.get("absolute_delta", 0)
    if percent_change is not None and absolute_delta is not None:
        if percent_change >= 200 and absolute_delta >= 20:
            summary_notes.append(
                f"Rapid complaint growth (+{absolute_delta:,} / {percent_change:+.0f}%)"
            )

    weekly_avg_to = growth.get("weekly_avg_to")
    weekly_avg_from = growth.get("weekly_avg_from")
    if weekly_avg_to is not None and weekly_avg_from is not None:
        delta_weekly = weekly_avg_to - weekly_avg_from
        if delta_weekly > 1:
            summary_notes.append(
                f"Weekly volume +{delta_weekly:.1f}/wk (from {weekly_avg_from:.1f} to {weekly_avg_to:.1f})"
            )

    if not summary_notes:
        summary_notes.append(priority_info.get("trigger_reason", "No spike trigger"))

    return {
        "priority": priority_info.get("priority_name"),
        "spike_axis": spike_axis,
        "notes": summary_notes,
    }


def _analyze_subcategory_drivers(
    from_data: pd.DataFrame,
    to_data: pd.DataFrame,
    subcategory_cols: List[str],
    absolute_delta: int,
    top_n: int = 3,
    min_delta: int = 1,
) -> Dict:
    """Analyze which subcategories drove the transition."""
    drivers_by_subcategory = {}

    for subcat_col in subcategory_cols:
        if subcat_col not in from_data.columns and subcat_col not in to_data.columns:
            continue

        # aggregate by subcategory
        if subcat_col in from_data.columns:
            from_subcat = (
                from_data.groupby(subcat_col)
                .size()
                .reset_index(name="count")
                .sort_values("count", ascending=False)
            )
        else:
            from_subcat = pd.DataFrame(columns=[subcat_col, "count"])

        if subcat_col in to_data.columns:
            to_subcat = (
                to_data.groupby(subcat_col)
                .size()
                .reset_index(name="count")
                .sort_values("count", ascending=False)
            )
        else:
            to_subcat = pd.DataFrame(columns=[subcat_col, "count"])

        # merge and calculate deltas
        comparison = pd.merge(
            from_subcat,
            to_subcat,
            on=subcat_col,
            how="outer",
            suffixes=("_from", "_to"),
        ).fillna(0)

        comparison["delta"] = comparison["count_to"] - comparison["count_from"]
        if absolute_delta > 0:
            comparison["percent_of_change"] = comparison["delta"] / absolute_delta * 100
        else:
            comparison["percent_of_change"] = 0.0

        # classify driver type
        def classify_driver_type(row):
            if row["count_from"] == 0:
                return "new_emergence"
            elif row["delta"] > row["count_from"]:
                return "acceleration"
            else:
                return "deceleration"

        comparison["driver_type"] = comparison.apply(classify_driver_type, axis=1)

        min_threshold = max(1, min_delta)
        filtered = comparison[comparison["delta"] >= min_threshold]
        top_drivers = filtered.nlargest(top_n, "delta").to_dict("records")

        drivers_list = []
        for driver in top_drivers:
            drivers_list.append(
                {
                    "name": driver[subcat_col],
                    "count_from": int(driver["count_from"]),
                    "count_to": int(driver["count_to"]),
                    "delta": int(driver["delta"]),
                    "percent_of_change": round(driver["percent_of_change"], 1),
                    "driver_type": driver["driver_type"],
                }
            )

        # calculate explanation power (share of cumulative volume delta)
        if absolute_delta > 0:
            top_explain_pct = (
                sum(d["delta"] for d in drivers_list) / absolute_delta * 100
            )
        else:
            top_explain_pct = 0.0

        drivers_by_subcategory[subcat_col] = {
            "top_drivers": drivers_list,
            "top_n_explain_pct": round(top_explain_pct, 1),
        }

    return drivers_by_subcategory


def display_transition_drivers(analysis: Dict) -> None:
    """Print a concise, diagnoser-style summary of transition drivers."""

    trans = analysis["transition"]
    mag = analysis["magnitude"]
    vol = mag["volume_change"]
    growth = mag["growth_change"]
    priority = analysis["priority"]
    spike = analysis.get("spike_drivers", {})
    subcats = analysis.get("subcategory_drivers", {})

    print()
    print("TRANSITION DRIVER ANALYSIS")

    # headline
    print(
        f"[P{priority['priority']}] {trans['entity']}: "
        f"{trans['from_quarter']} -> {trans['to_quarter']} "
        f"({trans.get('from_quadrant', '')} -> {trans.get('to_quadrant', '')})"
    )
    if trans.get("risk_level_change"):
        print(f"  Risk: {trans['risk_level_change']}")

    # core metrics
    print(
        "  Cumulative volume (all time): "
        f"{vol['count_from']:,} -> {vol['count_to']:,} "
        f"(Δ {vol['absolute_delta']:+,}, {vol['percent_change']:+.1f}%)"
    )
    print(
        "  X/Y:    "
        f"X {vol['x_from']:.2f} -> {vol['x_to']:.2f} (Δ {vol['x_delta']:+.2f}), "
        f"Y {growth['y_from']:.2f} -> {growth['y_to']:.2f} (Δ {growth['y_delta']:+.2f})"
    )
    if "period_counts" in mag:
        pc = mag["period_counts"]
        print(
            "  Period volume (quarter): "
            f"{pc['count_from']} -> {pc['count_to']} "
            f"(Δ {pc['absolute_delta']:+})"
        )

    # priority + spike summary
    print(f"  Priority: P{priority['priority']} ({priority['priority_name']})")
    print(f"  Trigger:  {priority['trigger_reason']}")

    for note in spike.get("notes", []):
        print(f"  · {note}")

    # subcategory drivers (if available)
    for subcat_col, drivers_data in subcats.items():
        top_drivers = drivers_data.get("top_drivers", [])
        explain_pct = drivers_data.get(
            "top_n_explain_pct", drivers_data.get("top_3_explain_pct", 0.0)
        )
        if not top_drivers:
            continue

        print(f"  Drivers by {subcat_col} (explain {explain_pct:.1f}% of change):")
        for d in top_drivers:
            print(
                f"    - {d['name']}: "
                f"{d['count_from']:,} -> {d['count_to']:,} "
                f"(Δ {d['delta']:+,}, {d['percent_of_change']:.1f}%, {d['driver_type']})"
            )

    print()  # trailing newline for readability
