"""Descriptive count breakdowns associated with saved quadrant transitions."""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple, Set, Union
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
            if (
                pd.api.types.is_object_dtype(series)
                or pd.api.types.is_string_dtype(series)
                or isinstance(series.dtype, pd.CategoricalDtype)
            ):
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
    Return the calendar-quarter raw-event window for a saved quarterly label.

    The start is inclusive and the end is exclusive. Monthly labels remain
    unsupported by this driver helper; movement and AutoViz period labels are
    not remapped here.

    Args:
        quarter_str: Quarter in format "YYYY-QN" (e.g., "2024-Q3")

    Returns:
        Tuple of (start_date, end_date) as ISO strings

    Examples:
        >>> _calculate_quarter_dates("2024-Q3")
        ('2024-07-01', '2024-10-01')
    """
    match = re.fullmatch(r"(\d{4})-Q([1-4])", quarter_str) if isinstance(quarter_str, str) else None
    if not match:
        raise ValueError(
            f"Invalid quarter format: {quarter_str}. Use 'YYYY-QN' (e.g., '2024-Q3')"
        )

    year = int(match.group(1))
    quarter = int(match.group(2))

    if quarter not in {1, 2, 3, 4}:
        raise ValueError(f"Quarter must be 1-4, got: {quarter}")

    start_date = datetime(year, (quarter - 1) * 3 + 1, 1)
    end_date = datetime(year + (quarter == 4), (quarter % 4) * 3 + 1, 1)

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
        (1, 'Critical: Extreme movement (dX=0.50, dY=0.50)', 'XY')
    """
    is_borderline = abs(x) <= 0.1 or abs(y) <= 0.1
    to_critical = to_quadrant == "Q1"

    # Fixed operational heuristic; no distributional sigma equivalence is assumed.
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
    period_from: str = None,
    period_to: str = None,
    entity_col: str = "entity",
    timestamp_col: str = "date",
    subcategory_cols: Optional[List[str]] = None,
    numeric_cols: Optional[Dict[str, Union[List[float], int]]] = None,
    top_n: int = 5,
    min_delta: int = 2,
    # backwards compat aliases
    quarter_from: str = None,
    quarter_to: str = None,
    top_n_subcategories: int = None,
    min_subcategory_delta: int = None,
) -> Dict:
    """
    Describe event-count breakdowns associated with a quadrant transition.

    Compares count changes, saved score changes and associated sub-categories.
    This is descriptive, not causal attribution. Raw-event windows use matching
    calendar quarters; reported weekly averages use a fixed 13-week divisor.
    See _calculate_quarter_dates before interpreting results.

    Args:
        movement_df: Output from track_movement(). Expected to
            contain the canonical period column ("quarter") whose labels
            must use quarterly labels ("YYYY-QN"). Monthly driver date
            conversion is not supported by this implementation.
        df_raw: Raw event data (pandas DataFrame)
        entity_name: Entity to analyze
        period_from: Saved quarterly label (e.g., "2024-Q2"); raw-event
            windows use the calendar mapping documented in _calculate_quarter_dates.
        period_to: Saved quarterly label (e.g., "2024-Q3").
        entity_col: Entity column name in df_raw
        timestamp_col: Timestamp column name in df_raw
        subcategory_cols: Explicit categorical column names; None auto-detects,
            and an empty list disables categorical breakdowns.
        numeric_cols: Dict of numeric columns to bin and analyze.
            - Explicit bins: {"amount": [0, 1e6, 5e6, 10e6]}
            - Auto quantiles: {"resolution_days": 4} (4 quantile bins)
        top_n: Number of increases and decreases to return per dimension.
        min_delta: Minimum absolute count change to include (at least one row).

    Returns:
        Dictionary with structure:
        {
            "transition": {...},           # Overview
            "magnitude": {...},            # Volume/growth changes
            "subcategory_drivers": {...},  # Drivers by categorical column
            "numeric_drivers": {...},      # Drivers by binned numeric column
            "priority": {...},             # Priority classification
            "meta": {...},                 # Diagnostic metadata
        }

        Each dimension retains top_drivers (increases) and adds top_decreases.
        Contributions and top_n_explain_pct divide signed deltas by the net
        raw-period count difference, not cumulative counts. Zero net change
        yields None; offsets can produce percentages beyond 100%. Coverage and
        reconciliation describe each dimension independently. Numeric bins
        report excluded missing/nonfinite/outside values by period.

    Examples:
        >>> # Basic analysis
        >>> analysis = extract_transition_drivers(
        ...     movement_df, df, "Service A", "2024-Q2", "2024-Q3",
        ...     entity_col="service", timestamp_col="date"
        ... )

        >>> # With categorical and numeric breakdowns
        >>> analysis = extract_transition_drivers(
        ...     movement_df, df, "Product X", "2024-Q3", "2024-Q4",
        ...     subcategory_cols=["region", "gender"],
        ...     numeric_cols={"amount": [0, 1e6, 5e6], "days": 4},
        ... )
    """
    # backwards compatibility for renamed parameters
    if period_from is None and quarter_from is not None:
        period_from = quarter_from
    if period_to is None and quarter_to is not None:
        period_to = quarter_to
    if top_n_subcategories is not None:
        top_n = top_n_subcategories
    if min_subcategory_delta is not None:
        min_delta = min_subcategory_delta

    if period_from is None or period_to is None:
        raise ValueError("period_from and period_to are required")

    if not isinstance(movement_df, pd.DataFrame) or not isinstance(df_raw, pd.DataFrame):
        raise TypeError("movement_df and df_raw must be pandas DataFrames")
    if not movement_df.columns.is_unique or not df_raw.columns.is_unique:
        raise ValueError("Input DataFrames must have unique column names")
    required_movement = {"entity", "quarter", "period_quadrant", "period_x", "period_y"}
    missing_movement = sorted(required_movement - set(movement_df.columns))
    if missing_movement:
        raise ValueError(f"movement_df is missing required columns: {missing_movement}")
    for col in (entity_col, timestamp_col):
        if col not in df_raw.columns:
            raise ValueError(f"df_raw is missing required column: {col!r}")
    if isinstance(top_n, bool) or not isinstance(top_n, int) or top_n < 1:
        raise ValueError("top_n must be a positive integer")
    if isinstance(min_delta, bool) or not isinstance(min_delta, (int, float)) or not np.isfinite(min_delta) or min_delta < 0:
        raise ValueError("min_delta must be non-negative")
    if subcategory_cols is not None:
        if not isinstance(subcategory_cols, list) or not all(isinstance(col, str) for col in subcategory_cols):
            raise ValueError("subcategory_cols must be a list of column names")
        invalid = [col for col in subcategory_cols if col not in df_raw.columns]
        if invalid:
            raise ValueError(f"Unknown subcategory columns: {invalid}")
    if numeric_cols is not None:
        if not isinstance(numeric_cols, dict):
            raise TypeError("numeric_cols must be a mapping of column names to bins")
        invalid = [col for col in numeric_cols if col not in df_raw.columns]
        if invalid:
            raise ValueError(f"Unknown numeric columns: {invalid}")

    movement_keys = movement_df[["entity", "quarter"]]
    if movement_keys.isna().any().any():
        raise ValueError("movement_df entity and quarter values must not be missing")
    if movement_keys.duplicated().any():
        duplicate_keys = movement_keys[movement_keys.duplicated(keep=False)].drop_duplicates().to_dict("records")
        raise ValueError(f"movement_df has duplicate entity-period rows: {duplicate_keys}")

    df_raw = df_raw.copy()
    try:
        df_raw[timestamp_col] = pd.to_datetime(df_raw[timestamp_col], errors="raise")
    except (TypeError, ValueError) as exc:
        raise ValueError(f"df_raw timestamp column {timestamp_col!r} contains invalid dates") from exc
    if df_raw[timestamp_col].isna().any():
        raise ValueError(f"df_raw timestamp column {timestamp_col!r} contains missing dates")
    if df_raw[entity_col].isna().any():
        raise ValueError(f"df_raw entity column {entity_col!r} contains missing identifiers")
    if not pd.api.types.is_datetime64_any_dtype(df_raw[timestamp_col]):
        raise ValueError(f"df_raw timestamp column {timestamp_col!r} must use one timezone")

    # get transition data from movement_df
    period_col = "quarter"
    entity_data = movement_df[movement_df["entity"] == entity_name]

    if len(entity_data) == 0:
        raise ValueError(f"Entity '{entity_name}' not found in movement data")

    from_data = entity_data[entity_data[period_col] == period_from]
    to_data = entity_data[entity_data[period_col] == period_to]

    if len(from_data) == 0:
        raise ValueError(f"Period '{period_from}' not found for '{entity_name}'")
    if len(to_data) == 0:
        raise ValueError(f"Period '{period_to}' not found for '{entity_name}'")

    from_row = from_data.iloc[0]
    to_row = to_data.iloc[0]
    for row in (from_row, to_row):
        for col in ("period_x", "period_y"):
            if not isinstance(row[col], (int, float, np.number)) or not np.isfinite(row[col]):
                raise ValueError(f"movement_df {col} must contain finite numeric scores")
        if not isinstance(row["period_quadrant"], str) or not re.fullmatch(r"Q[1-4](?:\*(?:XY|X|Y))?", row["period_quadrant"]):
            raise ValueError("movement_df period_quadrant must contain Q1–Q4 labels")
        if "cumulative_count" in row.index:
            count = row["cumulative_count"]
            if not isinstance(count, (int, float, np.number)) or not np.isfinite(count) or count < 0 or count != int(count):
                raise ValueError("movement_df cumulative_count must contain non-negative integer counts")

    from_quadrant = from_row["period_quadrant"]
    to_quadrant = to_row["period_quadrant"]

    # period-specific complaints (per quarter) for hybrid analysis
    from_start, from_end = _calculate_quarter_dates(period_from)
    to_start, to_end = _calculate_quarter_dates(period_to)
    if period_from >= period_to:
        raise ValueError("period_from must precede period_to")
    timezone = df_raw[timestamp_col].dt.tz

    def boundary(value: str) -> pd.Timestamp:
        return pd.Timestamp(value, tz=timezone)

    entity_complaints = df_raw[df_raw[entity_col] == entity_name]

    from_period_data = entity_complaints[
        (entity_complaints[timestamp_col] >= boundary(from_start))
        & (entity_complaints[timestamp_col] < boundary(from_end))
    ]

    to_period_data = entity_complaints[
        (entity_complaints[timestamp_col] >= boundary(to_start))
        & (entity_complaints[timestamp_col] < boundary(to_end))
    ]

    from_period_count = len(from_period_data)
    to_period_count = len(to_period_data)
    period_increase = to_period_count - from_period_count
    weeks_per_quarter = 13

    # transition overview
    transition_overview = {
        "entity": entity_name,
        "from_quarter": period_from,
        "to_quarter": period_to,
        "from_quadrant": from_quadrant,
        "to_quadrant": to_quadrant,
        "quadrant_changed": from_quadrant != to_quadrant,
        "from_quadrant_label": _get_quadrant_label(from_quadrant),
        "to_quadrant_label": _get_quadrant_label(to_quadrant),
        "risk_level_change": f"{_get_risk_level(from_quadrant)} -> {_get_risk_level(to_quadrant)}",
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
    if subcategory_cols == []:
        effective_subcats, auto_detected_subcats = [], False

    if effective_subcats:
        result["subcategory_drivers"] = _analyze_subcategory_drivers(
            from_period_data,
            to_period_data,
            effective_subcats,
            period_increase,
            top_n=top_n,
            min_delta=min_delta,
        )

    # numeric column analysis
    if numeric_cols:
        result["numeric_drivers"] = _analyze_numeric_drivers(
            from_period_data,
            to_period_data,
            numeric_cols,
            period_increase,
            top_n=top_n,
            min_delta=min_delta,
        )

    result["meta"] = {
        "subcategory_columns_used": effective_subcats,
        "subcategory_columns_auto_detected": auto_detected_subcats,
        "custom_driver_columns_loaded": bool(custom_driver_aliases),
        "numeric_columns_used": list(numeric_cols.keys()) if numeric_cols else [],
        "percentage_basis": "net_raw_period_count_change",
        "percentage_denominator": period_increase,
        "period_windows": {"from": [from_start, from_end], "to": [to_start, to_end]},
        "weeks_per_quarter": weeks_per_quarter,
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


def _driver_percent(delta: int, net_change: int) -> Optional[float]:
    """Return a signed contribution to the net period change."""
    if net_change == 0:
        return None
    return round(delta / net_change * 100, 1)


def _coverage_percent(value: int, total: int) -> Optional[float]:
    """Return coverage for one direction of the category deltas."""
    if total == 0:
        return None
    return round(value / total * 100, 1)


def _category_counts(data: pd.DataFrame, column: str) -> Dict:
    """Count categories while retaining missing values as a display value."""
    series = data[column]
    counts = series[series.notna()].value_counts()
    rows = {}
    for value, count in counts.items():
        rows[("value", type(value).__name__, repr(value))] = {
                "value": value,
                "count": int(count),
                "sort_key": (str(value), type(value).__name__, repr(value)),
            }
    if series.isna().any():
        rows[("missing",)] = {"value": None, "count": int(series.isna().sum()),
                              "sort_key": ("", "missing", "")}
    return rows


def _driver_summary(
    comparison: pd.DataFrame,
    *,
    value_key: str,
    net_change: int,
    top_n: int,
    min_delta: int,
    include_type: bool = False,
) -> Dict:
    """Build additive increase/decrease lists and reconciliation metadata."""
    threshold = max(1, min_delta)
    comparison = comparison.copy()
    comparison["delta"] = comparison["count_to"] - comparison["count_from"]
    comparison["percent_of_change"] = comparison["delta"].map(
        lambda delta: _driver_percent(int(delta), net_change)
    )
    if include_type:
        comparison["driver_type"] = np.select(
            [comparison["count_from"].eq(0), comparison["delta"].gt(comparison["count_from"])],
            ["new_emergence", "acceleration"],
            default="deceleration",
        )

    increase = comparison[comparison["delta"] >= threshold].copy()
    decrease = comparison["delta"] <= -threshold
    decrease = comparison[decrease].copy()
    increase = increase.sort_values(["delta", "sort_key"], ascending=[False, True], kind="stable").head(top_n)
    decrease = decrease.assign(_magnitude=decrease["delta"].abs()).sort_values(
        ["_magnitude", "sort_key"], ascending=[False, True], kind="stable"
    ).head(top_n)

    def serialize(row: pd.Series) -> Dict:
        item = {
            value_key: row["value"],
            "count_from": int(row["count_from"]),
            "count_to": int(row["count_to"]),
            "delta": int(row["delta"]),
            "percent_of_change": _driver_percent(int(row["delta"]), net_change),
        }
        if include_type:
            item["driver_type"] = row["driver_type"]
        return item

    increase_rows = [serialize(row) for _, row in increase.iterrows()]
    decrease_rows = [serialize(row) for _, row in decrease.iterrows()]
    all_delta = int(comparison["delta"].sum())
    increase_total = int(comparison.loc[comparison["delta"] > 0, "delta"].sum())
    decrease_total = int(-comparison.loc[comparison["delta"] < 0, "delta"].sum())
    selected_increase = sum(item["delta"] for item in increase_rows)
    selected_decrease = sum(item["delta"] for item in decrease_rows)
    return {
        "top_drivers": increase_rows,
        "top_decreases": decrease_rows,
        "top_n_explain_pct": _driver_percent(selected_increase, net_change),
        "top_n_decrease_pct": _driver_percent(selected_decrease, net_change),
        "top_n_increase_coverage_pct": _coverage_percent(selected_increase, increase_total),
        "top_n_decrease_coverage_pct": _coverage_percent(-selected_decrease, decrease_total),
        "period_count_from": int(comparison["count_from"].sum()),
        "period_count_to": int(comparison["count_to"].sum()),
        "net_change": int(net_change),
        "percentage_basis": "net_raw_period_count_change",
        "percentage_denominator": int(net_change),
        "percentage_defined": net_change != 0,
        "reconciliation": {
            "delta_sum": all_delta,
            "unaccounted_delta": net_change - all_delta,
            "matches_net_change": all_delta == net_change,
        },
    }


def _analyze_subcategory_drivers(
    from_data: pd.DataFrame,
    to_data: pd.DataFrame,
    subcategory_cols: List[str],
    net_change: int,
    top_n: int = 3,
    min_delta: int = 1,
) -> Dict:
    """Analyze category changes against the raw period-count difference."""
    drivers_by_subcategory = {}
    for subcat_col in subcategory_cols:
        from_counts = _category_counts(from_data, subcat_col)
        to_counts = _category_counts(to_data, subcat_col)
        rows = []
        for key in from_counts.keys() | to_counts.keys():
            item = from_counts.get(key) or to_counts[key]
            rows.append({"value": item["value"], "sort_key": item["sort_key"],
                         "count_from": from_counts.get(key, {}).get("count", 0),
                         "count_to": to_counts.get(key, {}).get("count", 0)})
        comparison = pd.DataFrame(rows, columns=["value", "sort_key", "count_from", "count_to"])
        comparison["value"] = pd.Series([row["value"] for row in rows], dtype=object)
        summary = _driver_summary(
            comparison,
            value_key="name",
            net_change=net_change,
            top_n=top_n,
            min_delta=min_delta,
            include_type=True,
        )
        summary["coverage"] = {
            "from": {"total": len(from_data), "included": len(from_data),
                     "missing": int(from_data[subcat_col].isna().sum())},
            "to": {"total": len(to_data), "included": len(to_data),
                   "missing": int(to_data[subcat_col].isna().sum())},
        }
        drivers_by_subcategory[subcat_col] = summary
    return drivers_by_subcategory


def _validated_bin_spec(column: str, spec):
    """Validate bins even when both selected raw periods are empty."""
    if isinstance(spec, bool):
        raise ValueError(f"Numeric bins for {column!r} must be a positive integer or ordered edges")
    if isinstance(spec, int):
        if spec < 1:
            raise ValueError(f"Numeric bin count for {column!r} must be positive")
        return spec
    try:
        if not isinstance(spec, (list, tuple, np.ndarray)):
            raise ValueError
        edges = np.asarray(spec, dtype=float)
        if edges.ndim != 1 or len(edges) < 2 or not np.isfinite(edges).all() or not np.all(np.diff(edges) > 0):
            raise ValueError
    except (TypeError, ValueError):
        raise ValueError(f"Numeric bins for {column!r} must be finite, strictly increasing edges") from None
    return edges


def _analyze_numeric_drivers(
    from_data: pd.DataFrame,
    to_data: pd.DataFrame,
    numeric_cols: Dict[str, Union[List[float], int]],
    net_change: int,
    top_n: int = 5,
    min_delta: int = 1,
) -> Dict:
    """Count shared numeric bins and reconcile excluded values by period."""
    drivers_by_numeric = {}
    for column, spec in numeric_cols.items():
        spec = _validated_bin_spec(column, spec)
        values = []
        for data in (from_data, to_data):
            try:
                numeric = pd.to_numeric(data[column], errors="raise").astype(float)
            except (ValueError, TypeError):
                raise ValueError(f"Numeric column {column!r} contains non-numeric values") from None
            values.append(numeric)
        combined = pd.concat(values, ignore_index=True)
        finite = combined[np.isfinite(combined)]
        constant = False
        if isinstance(spec, int):
            if finite.empty:
                edges = np.array([], dtype=float)
            elif finite.nunique() == 1:
                constant = True
                edges = np.array([finite.iloc[0], finite.iloc[0]])
            else:
                edges = np.unique(np.quantile(finite, np.linspace(0, 1, spec + 1)))
        else:
            edges = spec
        labels = [
            f"{'[' if i == 0 else '('}{float(low)!r}, {float(high)!r}]"
            for i, (low, high) in enumerate(zip(edges[:-1], edges[1:]))
        ]
        counts = []
        coverage = {}
        for direction, numeric in zip(("from", "to"), values):
            missing = numeric.isna()
            nonfinite = numeric.notna() & ~np.isfinite(numeric)
            outside = np.isfinite(numeric) & ((numeric < edges[0]) | (numeric > edges[-1])) if len(edges) else pd.Series(False, index=numeric.index)
            if constant:
                bin_counts = [int(numeric.eq(edges[0]).sum())]
            elif len(edges):
                codes = pd.cut(numeric.where(np.isfinite(numeric)), bins=edges, labels=False, include_lowest=True)
                bin_counts = [int(codes.eq(i).sum()) for i in range(len(labels))]
            else:
                bin_counts = []
            counts.append(bin_counts)
            coverage[direction] = {
                "total": len(numeric), "included": sum(bin_counts),
                "missing": int(missing.sum()), "nonfinite": int(nonfinite.sum()),
                "outside_bins": int(outside.sum()),
            }
        comparison = pd.DataFrame({
            "value": labels,
            "count_from": counts[0], "count_to": counts[1],
            "sort_key": list(range(len(labels))),
        })
        summary = _driver_summary(comparison, value_key="bin", net_change=net_change,
                                  top_n=top_n, min_delta=min_delta)
        summary["bin_edges"] = [float(edge) for edge in edges]
        summary["period_count_from"] = len(from_data)
        summary["period_count_to"] = len(to_data)
        summary["coverage"] = coverage
        summary["excluded_values"] = {
            key: sum(coverage[d][key] for d in ("from", "to"))
            for key in ("missing", "nonfinite", "outside_bins")
        }
        summary["excluded_values"]["total"] = sum(summary["excluded_values"].values())
        excluded_delta = (coverage["to"]["total"] - coverage["to"]["included"]
                          - coverage["from"]["total"] + coverage["from"]["included"])
        reconciliation = summary["reconciliation"]
        reconciliation["excluded_delta"] = excluded_delta
        reconciliation["matches_net_change"] = reconciliation["delta_sum"] + excluded_delta == net_change
        reconciliation["unaccounted_delta"] = net_change - reconciliation["delta_sum"] - excluded_delta
        drivers_by_numeric[column] = summary
    return drivers_by_numeric


def display_transition_drivers(
    analysis: Dict,
    save_txt: bool = False,
    txt_path: Optional[str] = None,
    txt_mode: str = "a",
) -> None:
    """Print a concise, diagnoser-style summary of transition drivers.

    Args:
        analysis: Output from extract_transition_drivers()
        save_txt: Save output to text file (default: False)
        txt_path: Path for text file (required if save_txt=True)
        txt_mode: File mode - "a" to append (default), "w" to overwrite
    """
    trans = analysis["transition"]
    mag = analysis["magnitude"]
    vol = mag["volume_change"]
    growth = mag["growth_change"]
    priority = analysis["priority"]
    spike = analysis.get("spike_drivers", {})
    subcats = analysis.get("subcategory_drivers", {})

    lines = []
    lines.append("")
    lines.append("TRANSITION DRIVER ANALYSIS")

    # headline
    lines.append(
        f"[P{priority['priority']}] {trans['entity']}: "
        f"{trans['from_quarter']} -> {trans['to_quarter']} "
        f"({trans.get('from_quadrant', '')} -> {trans.get('to_quadrant', '')})"
    )
    if trans.get("risk_level_change"):
        lines.append(f"  Risk: {trans['risk_level_change']}")

    # core metrics
    lines.append(
        "  Cumulative volume (all time): "
        f"{vol['count_from']:,} -> {vol['count_to']:,} "
        f"(Δ {vol['absolute_delta']:+,}, {vol['percent_change']:+.1f}%)"
    )
    lines.append(
        "  X/Y:    "
        f"X {vol['x_from']:.2f} -> {vol['x_to']:.2f} (Δ {vol['x_delta']:+.2f}), "
        f"Y {growth['y_from']:.2f} -> {growth['y_to']:.2f} (Δ {growth['y_delta']:+.2f})"
    )
    if "period_counts" in mag:
        pc = mag["period_counts"]
        lines.append(
            "  Period volume (quarter): "
            f"{pc['count_from']} -> {pc['count_to']} "
            f"(Δ {pc['absolute_delta']:+})"
        )

    # priority + spike summary
    lines.append(f"  Priority: P{priority['priority']} ({priority['priority_name']})")
    lines.append(f"  Trigger:  {priority['trigger_reason']}")

    for note in spike.get("notes", []):
        lines.append(f"  · {note}")

    def format_pct(value: Optional[float]) -> str:
        return "not defined" if value is None else f"{value:.1f}%"

    # subcategory drivers
    for subcat_col, drivers_data in subcats.items():
        top_drivers = drivers_data.get("top_drivers", [])
        explain_pct = drivers_data.get(
            "top_n_explain_pct", drivers_data.get("top_3_explain_pct", 0.0)
        )
        top_decreases = drivers_data.get("top_decreases", [])
        if not top_drivers and not top_decreases:
            continue

        lines.append(f"  Drivers by {subcat_col} (increases: {format_pct(explain_pct)} of net period change):")
        for d in top_drivers:
            lines.append(
                f"    - {d['name']}: "
                f"{d['count_from']:,} -> {d['count_to']:,} "
                f"(Δ {d['delta']:+,}, {format_pct(d['percent_of_change'])}, {d['driver_type']})"
            )
        for d in top_decreases:
            lines.append(
                f"    - decrease {d['name']}: {d['count_from']:,} -> {d['count_to']:,} "
                f"(Δ {d['delta']:+,}, {format_pct(d['percent_of_change'])})"
            )

    # numeric drivers
    numerics = analysis.get("numeric_drivers", {})
    for col_name, drivers_data in numerics.items():
        top_drivers = drivers_data.get("top_drivers", [])
        explain_pct = drivers_data.get("top_n_explain_pct", 0.0)
        top_decreases = drivers_data.get("top_decreases", [])
        if not top_drivers and not top_decreases:
            continue

        lines.append(f"  Drivers by {col_name} (increases: {format_pct(explain_pct)} of net period change):")
        for d in top_drivers:
            lines.append(
                f"    - {d['bin']}: "
                f"{d['count_from']:,} -> {d['count_to']:,} "
                f"(Δ {d['delta']:+,}, {format_pct(d['percent_of_change'])})"
            )
        for d in top_decreases:
            lines.append(
                f"    - decrease {d['bin']}: {d['count_from']:,} -> {d['count_to']:,} "
                f"(Δ {d['delta']:+,}, {format_pct(d['percent_of_change'])})"
            )

    lines.append("")  # trailing newline

    # output
    text = "\n".join(lines)
    print(text)

    if save_txt and txt_path:
        with open(txt_path, txt_mode, encoding="utf-8") as f:
            f.write(text + "\n")
