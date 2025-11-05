"""Transition driver analysis for identifying root causes of quadrant transitions."""

import pandas as pd
from typing import Dict, List, Optional, Tuple
from collections import Counter
import re
from datetime import datetime


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
    text_col: Optional[str] = None,
) -> Dict:
    """
    Extract key drivers of a quadrant transition.

    Analyzes what drove a specific entity to transition between quadrants,
    including volume changes, growth changes, and contributing sub-categories.

    Args:
        movement_df: Output from track_cumulative_movement()
        df_raw: Raw event data (pandas DataFrame)
        entity_name: Entity to analyze
        quarter_from: Starting quarter (e.g., "2024-Q2")
        quarter_to: Ending quarter (e.g., "2024-Q3")
        entity_col: Entity column name in df_raw
        timestamp_col: Timestamp column name in df_raw
        subcategory_cols: Optional list of subcategory columns to analyze
        text_col: Optional text column for keyword analysis

    Returns:
        Dictionary with structure:
        {
            "transition": {...},           # Overview
            "magnitude": {...},            # Volume/growth changes
            "subcategory_drivers": {...},  # Drivers by subcategory (if provided)
            "keyword_drivers": [...],      # Text analysis (if provided)
            "priority": {...}              # Priority classification
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
    entity_data = movement_df[movement_df["entity"] == entity_name]

    if len(entity_data) == 0:
        raise ValueError(f"Entity '{entity_name}' not found in movement data")

    from_data = entity_data[entity_data["quarter"] == quarter_from]
    to_data = entity_data[entity_data["quarter"] == quarter_to]

    if len(from_data) == 0:
        raise ValueError(f"Quarter '{quarter_from}' not found for '{entity_name}'")
    if len(to_data) == 0:
        raise ValueError(f"Quarter '{quarter_to}' not found for '{entity_name}'")

    from_row = from_data.iloc[0]
    to_row = to_data.iloc[0]

    from_quadrant = from_row["period_quadrant"]
    to_quadrant = to_row["period_quadrant"]

    # transition overview
    transition_overview = {
        "entity": entity_name,
        "from_quarter": quarter_from,
        "to_quarter": quarter_to,
        "from_quadrant": from_quadrant,
        "to_quadrant": to_quadrant,
        "quadrant_changed": from_quadrant != to_quadrant,
    }

    # magnitude metrics
    if "complaints_to_date" in from_row.index:
        count_col_name = "complaints_to_date"
    elif "count_to_date" in from_row.index:
        count_col_name = "count_to_date"
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

    # initialize result
    result = {
        "transition": transition_overview,
        "magnitude": magnitude_metrics,
        "priority": priority_classification,
    }

    # subcategory drivers (optional)
    if subcategory_cols:
        result["subcategory_drivers"] = _analyze_subcategory_drivers(
            df_raw,
            entity_name,
            entity_col,
            timestamp_col,
            quarter_from,
            quarter_to,
            subcategory_cols,
            absolute_delta,
        )

    # keyword drivers (optional)
    if text_col:
        result["keyword_drivers"] = _analyze_keyword_drivers(
            df_raw,
            entity_name,
            entity_col,
            timestamp_col,
            quarter_from,
            quarter_to,
            text_col,
        )

    return result


def _analyze_subcategory_drivers(
    df_raw: pd.DataFrame,
    entity_name: str,
    entity_col: str,
    timestamp_col: str,
    quarter_from: str,
    quarter_to: str,
    subcategory_cols: List[str],
    period_increase: int,
) -> Dict:
    """Analyze which subcategories drove the transition."""
    from_start, from_end = _calculate_quarter_dates(quarter_from)
    to_start, to_end = _calculate_quarter_dates(quarter_to)

    # filter to entity and quarters
    entity_data = df_raw[df_raw[entity_col] == entity_name]

    from_data = entity_data[
        (entity_data[timestamp_col] >= pd.Timestamp(from_start))
        & (entity_data[timestamp_col] < pd.Timestamp(from_end))
    ]

    to_data = entity_data[
        (entity_data[timestamp_col] >= pd.Timestamp(to_start))
        & (entity_data[timestamp_col] < pd.Timestamp(to_end))
    ]

    drivers_by_subcategory = {}

    for subcat_col in subcategory_cols:
        if subcat_col not in df_raw.columns:
            continue

        # aggregate by subcategory
        from_subcat = (
            from_data.groupby(subcat_col)
            .size()
            .reset_index(name="count")
            .sort_values("count", ascending=False)
        )

        to_subcat = (
            to_data.groupby(subcat_col)
            .size()
            .reset_index(name="count")
            .sort_values("count", ascending=False)
        )

        # merge and calculate deltas
        comparison = pd.merge(
            from_subcat,
            to_subcat,
            on=subcat_col,
            how="outer",
            suffixes=("_from", "_to"),
        ).fillna(0)

        comparison["delta"] = comparison["count_to"] - comparison["count_from"]
        comparison["percent_of_change"] = (
            (comparison["delta"] / period_increase * 100) if period_increase > 0 else 0
        )

        # classify driver type
        def classify_driver_type(row):
            if row["count_from"] == 0:
                return "new_emergence"
            elif row["delta"] > row["count_from"]:
                return "acceleration"
            else:
                return "deceleration"

        comparison["driver_type"] = comparison.apply(classify_driver_type, axis=1)

        # get top 3 by absolute delta
        top_drivers = (
            comparison[comparison["delta"] > 0].nlargest(3, "delta").to_dict("records")
        )

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

        # calculate explanation power
        top_explain_pct = (
            sum([d["delta"] for d in drivers_list]) / period_increase * 100
            if period_increase > 0
            else 0
        )

        drivers_by_subcategory[subcat_col] = {
            "top_drivers": drivers_list,
            "top_3_explain_pct": round(top_explain_pct, 1),
        }

    return drivers_by_subcategory


def _analyze_keyword_drivers(
    df_raw: pd.DataFrame,
    entity_name: str,
    entity_col: str,
    timestamp_col: str,
    quarter_from: str,
    quarter_to: str,
    text_col: str,
    top_n: int = 10,
) -> List[Dict]:
    """Extract emerging keywords from text using bigram analysis."""
    from_start, from_end = _calculate_quarter_dates(quarter_from)
    to_start, to_end = _calculate_quarter_dates(quarter_to)

    # filter to entity and quarters
    entity_data = df_raw[df_raw[entity_col] == entity_name]

    from_data = entity_data[
        (entity_data[timestamp_col] >= pd.Timestamp(from_start))
        & (entity_data[timestamp_col] < pd.Timestamp(from_end))
    ]

    to_data = entity_data[
        (entity_data[timestamp_col] >= pd.Timestamp(to_start))
        & (entity_data[timestamp_col] < pd.Timestamp(to_end))
    ]

    def extract_bigrams(text: str) -> List[str]:
        """Extract meaningful bigrams from text."""
        if not text or pd.isna(text):
            return []

        text = str(text).lower()
        words = re.findall(r"\b\w+\b", text)

        # basic stopwords (language-agnostic)
        stopwords = {
            "the",
            "is",
            "in",
            "to",
            "of",
            "and",
            "a",
            "an",
            "with",
            "that",
            "this",
            "has",
            "have",
            "been",
            "was",
            "were",
            "are",
            "will",
            "would",
            "could",
            "for",
            "from",
            "by",
            "on",
            "at",
            "as",
            "be",
            "it",
            "or",
            "not",
        }

        # filter short words and stopwords
        words = [w for w in words if len(w) > 2 and w not in stopwords]

        # create bigrams
        bigrams = [f"{words[i]} {words[i + 1]}" for i in range(len(words) - 1)]

        # filter numeric-only bigrams
        bigrams = [b for b in bigrams if not all(c.isdigit() or c == " " for c in b)]

        return bigrams

    # extract bigrams
    from_text = from_data[text_col].tolist()
    to_text = to_data[text_col].tolist()

    from_bigrams = []
    for text in from_text:
        from_bigrams.extend(extract_bigrams(text))

    to_bigrams = []
    for text in to_text:
        to_bigrams.extend(extract_bigrams(text))

    # count frequency
    from_counter = Counter(from_bigrams)
    to_counter = Counter(to_bigrams)

    # find bigrams that increased most
    bigram_changes = {}
    for bigram in set(list(from_counter.keys()) + list(to_counter.keys())):
        from_count = from_counter.get(bigram, 0)
        to_count = to_counter.get(bigram, 0)
        delta = to_count - from_count
        if delta > 0:
            bigram_changes[bigram] = {
                "from": from_count,
                "to": to_count,
                "delta": delta,
            }

    # get top N emerging bigrams
    top_bigrams = sorted(
        bigram_changes.items(), key=lambda x: x[1]["delta"], reverse=True
    )[:top_n]

    keyword_drivers = []
    for bigram, stats in top_bigrams:
        keyword_drivers.append(
            {
                "bigram": bigram,
                "frequency_from": stats["from"],
                "frequency_to": stats["to"],
                "delta": stats["delta"],
            }
        )

    return keyword_drivers


def display_transition_drivers(analysis: Dict, show_keywords: bool = False) -> None:
    """
    Print transition driver analysis in human-readable format.

    Args:
        analysis: Output from extract_transition_drivers()
        show_keywords: Whether to show keyword analysis

    Examples:
        >>> display_transition_drivers(analysis)
    """
    trans = analysis["transition"]
    mag = analysis["magnitude"]
    vol = mag["volume_change"]
    growth = mag["growth_change"]
    priority = analysis["priority"]

    print()
    print("TRANSITION DRIVER ANALYSIS")

    # transition overview
    print()
    print(f"Entity: {trans['entity']}")
    print(f"Period: {trans['from_quarter']} -> {trans['to_quarter']}")
    print(f"Quadrant: {trans['from_quadrant']} -> {trans['to_quadrant']}")

    if trans["quadrant_changed"]:
        print("Status: Quadrant transition detected")
    else:
        print("Status: Within-quadrant movement")

    # priority
    print()
    print(f"Priority: P{priority['priority']} ({priority['priority_name']})")
    print(f"Reason: {priority['trigger_reason']}")
    if priority.get("spike_axis"):
        print(f"Spike axis: {priority['spike_axis']}")

    # magnitude
    print()
    print("Magnitude:")
    print(
        f"  Volume: {vol['count_from']:,} -> {vol['count_to']:,} "
        f"(delta {vol['absolute_delta']:+,}, {vol['percent_change']:+.1f}%)"
    )
    print(
        f"  X-axis: {vol['x_from']:.2f} -> {vol['x_to']:.2f} (delta {vol['x_delta']:+.2f})"
    )
    print(
        f"  Y-axis: {growth['y_from']:.2f} -> {growth['y_to']:.2f} (delta {growth['y_delta']:+.2f})"
    )

    # subcategory drivers
    if "subcategory_drivers" in analysis:
        for subcat_col, drivers_data in analysis["subcategory_drivers"].items():
            top_drivers = drivers_data["top_drivers"]
            explain_pct = drivers_data["top_3_explain_pct"]

            if top_drivers:
                print()
                print(
                    f"Top drivers by {subcat_col} (explain {explain_pct:.1f}% of change):"
                )
                for i, driver in enumerate(top_drivers, 1):
                    print(f"  {i}. {driver['name']}")
                    print(
                        f"     {driver['count_from']:,} -> {driver['count_to']:,} "
                        f"(delta {driver['delta']:+,}, {driver['percent_of_change']:.1f}%)"
                    )
                    print(f"     Type: {driver['driver_type']}")

    # keyword drivers
    if show_keywords and "keyword_drivers" in analysis:
        keywords = analysis["keyword_drivers"]
        if keywords:
            print()
            print("Top emerging keywords:")
            for i, kw in enumerate(keywords[:5], 1):
                print(
                    f"  {i}. '{kw['bigram']}' ({kw['frequency_from']} -> {kw['frequency_to']}, delta +{kw['delta']})"
                )

    print()
