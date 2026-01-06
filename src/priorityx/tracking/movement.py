"""Cumulative movement tracking through priority quadrants."""

from datetime import timedelta
from typing import Optional, Sequence, Union

import pandas as pd

from priorityx.utils.helpers import latest_artifact_csv, save_dataframe_to_csv


def _is_quarter_start(ts: pd.Timestamp) -> bool:
    """Check if timestamp is the first day of a calendar quarter."""
    return ts.day == 1 and ts.month in (1, 4, 7, 10)


def _next_quarter_start(ts: pd.Timestamp) -> pd.Timestamp:
    """Get timestamp for the first day of the next calendar quarter."""
    if ts.month in (1, 4, 7, 10):
        month = ts.month
    else:
        # fallback to nearest lower quarter
        month = ((ts.month - 1) // 3) * 3 + 1
        ts = pd.Timestamp(year=ts.year, month=month, day=1)

    if month == 1:
        next_month = 4
        next_year = ts.year
    elif month == 4:
        next_month = 7
        next_year = ts.year
    elif month == 7:
        next_month = 10
        next_year = ts.year
    else:  # month == 10
        next_month = 1
        next_year = ts.year + 1

    return pd.Timestamp(year=next_year, month=next_month, day=1)


def _quarter_label(ts: pd.Timestamp) -> str:
    """Format timestamp into 'YYYY-QX' label."""
    quarter = ((ts.month - 1) // 3) + 1
    return f"{ts.year}-Q{quarter}"


def _is_month_start(ts: pd.Timestamp) -> bool:
    """Check if timestamp is the first day of a calendar month."""

    return ts.day == 1


def _next_month_start(ts: pd.Timestamp) -> pd.Timestamp:
    """Get timestamp for the first day of the next calendar month."""

    year = ts.year
    month = ts.month
    if month == 12:
        return pd.Timestamp(year=year + 1, month=1, day=1)
    return pd.Timestamp(year=year, month=month + 1, day=1)


def _month_label(ts: pd.Timestamp) -> str:
    """Format timestamp into 'YYYY-MM' label."""

    return ts.strftime("%Y-%m")


def _build_quarter_schedule_from_range(
    start_date: str, end_date: str
) -> list[tuple[str, str]]:
    """Build quarter schedule from date range.

    Args:
        start_date: Start date (YYYY-MM-DD), must be quarter boundary
        end_date: End date (YYYY-MM-DD), must be quarter boundary

    Returns:
        List of (label, exclusive_end_date) tuples

    Raises:
        ValueError: If dates are not quarter boundaries or invalid
    """
    start_ts = pd.Timestamp(start_date)
    end_ts = pd.Timestamp(end_date)

    if start_ts >= end_ts:
        raise ValueError("Start date must be earlier than end date")

    if not _is_quarter_start(start_ts) or not _is_quarter_start(end_ts):
        raise ValueError(
            "Dates must be quarter boundaries (YYYY-01-01, YYYY-04-01, "
            "YYYY-07-01, or YYYY-10-01)"
        )

    schedule = []
    current = start_ts
    while current < end_ts:
        next_start = _next_quarter_start(current)
        if next_start > end_ts:
            next_start = end_ts

        schedule.append((_quarter_label(current), next_start.strftime("%Y-%m-%d")))
        current = next_start

    return schedule


def _build_month_schedule_from_range(
    start_date: str, end_date: str
) -> list[tuple[str, str]]:
    """Build month schedule from date range.

    Args:
        start_date: Start date (YYYY-MM-DD), must be month boundary (day=1)
        end_date: End date (YYYY-MM-DD), must be month boundary (day=1)

    Returns:
        List of (label, exclusive_end_date) tuples

    Raises:
        ValueError: If dates are not month boundaries or invalid
    """

    start_ts = pd.Timestamp(start_date)
    end_ts = pd.Timestamp(end_date)

    if start_ts >= end_ts:
        raise ValueError("Start date must be earlier than end date")

    if not _is_month_start(start_ts) or not _is_month_start(end_ts):
        raise ValueError("Dates must be month boundaries (YYYY-MM-01)")

    schedule: list[tuple[str, str]] = []
    current = start_ts
    while current < end_ts:
        next_start = _next_month_start(current)
        if next_start > end_ts:
            next_start = end_ts

        schedule.append((_month_label(current), next_start.strftime("%Y-%m-%d")))
        current = next_start

    return schedule


def _build_default_quarter_schedule(
    df: pd.DataFrame, timestamp_col: str
) -> list[tuple[str, str]]:
    """
    Create default quarter schedule spanning the dataset.

    Args:
        df: Input pandas DataFrame
        timestamp_col: Column name for timestamp

    Returns:
        List of (label, exclusive_end_date) tuples
    """
    if timestamp_col not in df.columns or len(df) == 0:
        return []

    df = df.copy()
    df[timestamp_col] = pd.to_datetime(df[timestamp_col])

    min_date = df[timestamp_col].min()
    max_date = df[timestamp_col].max()

    if pd.isna(min_date) or pd.isna(max_date):
        return []

    start_ts = min_date.to_period("Q").to_timestamp(how="start")
    # exclusive boundary: first day of quarter following max_date
    max_quarter_start = max_date.to_period("Q").to_timestamp(how="start")
    end_ts = _next_quarter_start(max_quarter_start)

    return _build_quarter_schedule_from_range(
        start_ts.strftime("%Y-%m-%d"), end_ts.strftime("%Y-%m-%d")
    )


def _build_default_month_schedule(
    df: pd.DataFrame, timestamp_col: str
) -> list[tuple[str, str]]:
    """Create default month schedule spanning the dataset."""

    if timestamp_col not in df.columns or len(df) == 0:
        return []

    df = df.copy()
    df[timestamp_col] = pd.to_datetime(df[timestamp_col])

    min_date = df[timestamp_col].min()
    max_date = df[timestamp_col].max()

    if pd.isna(min_date) or pd.isna(max_date):
        return []

    start_ts = min_date.to_period("M").to_timestamp(how="start")
    max_month_start = max_date.to_period("M").to_timestamp(how="start")
    end_ts = _next_month_start(max_month_start)

    return _build_month_schedule_from_range(
        start_ts.strftime("%Y-%m-%d"), end_ts.strftime("%Y-%m-%d")
    )


def normalize_period_schedule(
    quarters: Optional[Sequence[Union[tuple[str, str], str]]],
    df: pd.DataFrame,
    timestamp_col: str,
    temporal_granularity: str = "quarterly",
) -> list[tuple[str, str]]:
    """Normalize period schedule to standard (label, cutoff_date) format.

    For quarterly granularity:
    1. Explicit schedule: [("2024-Q2", "2024-07-01"), ...]
    2. Date range: ["2024-01-01", "2025-10-01"]
    3. None: Auto-detect from data

    For monthly granularity, the same patterns apply but labels are
    "YYYY-MM" and dates must be month boundaries.
    """

    if temporal_granularity == "monthly":
        if quarters is None:
            return _build_default_month_schedule(df, timestamp_col)

        if len(quarters) == 0:
            return []

        # date range format: ["2024-01-01", "2025-10-01"]
        if len(quarters) == 2 and all(isinstance(q, str) for q in quarters):
            return _build_month_schedule_from_range(quarters[0], quarters[1])

        normalized_schedule: list[tuple[str, str]] = []
        for entry in quarters:
            if not isinstance(entry, tuple) or len(entry) != 2:
                raise ValueError(
                    "quarters must be a list of (label, cutoff_date) tuples "
                    "or two date boundary strings",
                )
            label, cutoff = entry
            normalized_schedule.append((label, cutoff))

        return normalized_schedule

    # default: quarterly schedule
    if quarters is None:
        return _build_default_quarter_schedule(df, timestamp_col)

    if len(quarters) == 0:
        return []

    # date range format: ["2024-01-01", "2025-10-01"]
    if len(quarters) == 2 and all(isinstance(q, str) for q in quarters):
        return _build_quarter_schedule_from_range(quarters[0], quarters[1])

    # explicit schedule format: [("2024-Q2", "2024-07-01"), ...]
    normalized_schedule2: list[tuple[str, str]] = []
    for entry in quarters:
        if not isinstance(entry, tuple) or len(entry) != 2:
            raise ValueError(
                "quarters must be a list of (label, cutoff_date) tuples "
                "or two quarter boundary strings",
            )
        label, cutoff = entry
        normalized_schedule2.append((label, cutoff))

    return normalized_schedule2


def normalize_quarter_schedule(
    quarters: Optional[Sequence[Union[tuple[str, str], str]]],
    df: pd.DataFrame,
    timestamp_col: str,
    temporal_granularity: str = "quarterly",
) -> list[tuple[str, str]]:
    """Backward-compatible alias for :func:`normalize_period_schedule`.

    Historically this helper only handled quarterly schedules; it now
    delegates to ``normalize_period_schedule`` which supports both
    quarterly and monthly granularities.
    """

    return normalize_period_schedule(
        quarters,
        df,
        timestamp_col,
        temporal_granularity=temporal_granularity,
    )


def track_cumulative_movement(
    df: pd.DataFrame,
    entity_col: str,
    timestamp_col: str,
    quarters: Optional[Sequence[Union[tuple[str, str], str]]] = None,
    min_total_count: int = 20,
    decline_window_quarters: int = 6,
    temporal_granularity: str = "quarterly",
    vcp_p: float = 3.5,
    fe_p: float = 3.0,
) -> tuple[pd.DataFrame, dict]:
    """
    Track entity movement through priority quadrants over time.

    Uses cumulative data periods to track X/Y movement while maintaining
    stable global baseline classification. Three-step process:

    1. Global baseline: GLMM on full dataset → stable quadrant assignment
    2. Endpoint cohorting: Define valid entities based on endpoint criteria
    3. Quarter-by-quarter tracking: Track X/Y movement for valid entities

    Args:
        df: Input pandas DataFrame
        entity_col: Column name for entity identifier
        timestamp_col: Column name for timestamp (datetime type)
        quarters: Period specification (see normalize_period_schedule)
        min_total_count: Minimum total count for inclusion (default: 20)
        decline_window_quarters: Max quarters after last observation (default: 6)
        temporal_granularity: Time granularity for GLMM ('quarterly', 'yearly', 'semiannual')
        vcp_p: Prior scale for random effects (default: 3.5)
        fe_p: Prior scale for fixed effects (default: 3.0)

    Returns:
        Tuple of (movement_df, metadata_dict)
        - movement_df: Period-by-period tracking with columns:
          [entity, quarter, period_count, cumulative_count, period_x, period_y,
           period_quadrant, global_quadrant, global_x, global_y,
           count_total, x_delta, y_delta, quadrant_differs]
          (the ``quarter`` column serves as the canonical period axis
          for both quarterly and monthly granularities)
        - metadata_dict: Tracking statistics and configuration

    Examples:
        >>> # auto-detect quarters from data
        >>> movement_df, meta = track_cumulative_movement(
        ...     df, entity_col="service", timestamp_col="date"
        ... )

        >>> # specify date range
        >>> movement_df, meta = track_cumulative_movement(
        ...     df, entity_col="service", timestamp_col="date",
        ...     quarters=["2024-01-01", "2025-01-01"]
        ... )
    """
    # ensure datetime type
    df = df.copy()
    df[timestamp_col] = pd.to_datetime(df[timestamp_col])

    # normalize quarter/month schedule (generic period schedule)
    period_schedule = normalize_period_schedule(
        quarters,
        df,
        timestamp_col,
        temporal_granularity=temporal_granularity,
    )

    period_col = "quarter"

    if len(period_schedule) == 0:
        print("Warning: No period boundaries available for cumulative tracking")
        empty_df = pd.DataFrame(
            columns=[
                "entity",
                period_col,
                "period_count",
                "cumulative_count",
                "period_x",
                "period_y",
                "period_quadrant",
                "global_quadrant",
                "global_x",
                "global_y",
                "count_total",
                "x_delta",
                "y_delta",
                "quadrant_differs",
            ]
        )

        metadata = {
            "entities_tracked": 0,
            "quarters_analyzed": 0,
            "total_observations": 0,
            "divergence_rate": 0.0,
            "temporal_granularity": temporal_granularity,
            "quarter_schedule": [],
        }
        return empty_df, metadata

    print("\nCUMULATIVE MOVEMENT TRACKING")

    # import fit_priority_matrix
    from ..core.glmm import fit_priority_matrix

    # step 1: calculate global baseline from full dataset
    print("\n[1/3] Calculating global baseline (FULL dataset)...")
    global_results, _ = fit_priority_matrix(
        df,
        entity_col=entity_col,
        timestamp_col=timestamp_col,
        min_observations=0,
        min_total_count=min_total_count,
        decline_window_quarters=0,  # don't filter for global baseline
        temporal_granularity=temporal_granularity,
        vcp_p=vcp_p,
        fe_p=fe_p,
    )

    print(f"Global baseline: {len(global_results)} entities")

    # create global baseline lookup
    global_baseline = {}
    for _, row in global_results.iterrows():
        entity = row[entity_col]
        global_baseline[entity] = {
            "global_quadrant": row["quadrant"],
            "global_x": row["x_score"],
            "global_y": row["y_score"],
            "count_total": row["count"],
        }

    # step 2: determine valid entities at analysis endpoint
    print("\n[2/3] Determining valid entities at analysis endpoint...")

    # get endpoint (last period in schedule)
    final_quarter_name, final_quarter_date = period_schedule[-1]
    print(f"Analysis endpoint: {final_quarter_name} ({final_quarter_date})")

    # calculate valid entities based on cumulative totals up to endpoint
    cumulative_up_to_endpoint = df[df[timestamp_col] < pd.Timestamp(final_quarter_date)]

    # apply filters in same order as fit_priority_matrix for consistency

    # step 1: filter by min_total_count
    endpoint_totals = (
        cumulative_up_to_endpoint.groupby(entity_col).size().reset_index(name="total")
    )
    entities_above_threshold = endpoint_totals[
        endpoint_totals["total"] >= min_total_count
    ][entity_col]
    cumulative_up_to_endpoint = cumulative_up_to_endpoint[
        cumulative_up_to_endpoint[entity_col].isin(entities_above_threshold)
    ]

    # step 2: apply decline_window filter
    if decline_window_quarters > 0:
        dataset_max_date = cumulative_up_to_endpoint[timestamp_col].max()
        decline_cutoff = dataset_max_date - timedelta(days=decline_window_quarters * 91)

        last_observation_at_endpoint = (
            cumulative_up_to_endpoint.groupby(entity_col)[timestamp_col]
            .max()
            .reset_index(name="last_date")
        )
        stale_entities_at_endpoint = last_observation_at_endpoint[
            last_observation_at_endpoint["last_date"] < decline_cutoff
        ][entity_col]
        cumulative_up_to_endpoint = cumulative_up_to_endpoint[
            ~cumulative_up_to_endpoint[entity_col].isin(stale_entities_at_endpoint)
        ]
        n_stale = len(stale_entities_at_endpoint)
        if n_stale > 0:
            print(
                f"  Filtered {n_stale} stale entities at endpoint "
                f"(inactive >{decline_window_quarters}Q)"
            )

    # get final entity list after filters
    valid_entity_list = cumulative_up_to_endpoint[entity_col].unique().tolist()

    n_valid_at_endpoint = len(valid_entity_list)
    print(
        f"  Valid entities (≥{min_total_count} count by {final_quarter_name}): "
        f"{n_valid_at_endpoint}"
    )

    # step 3: track movement through periods
    print(f"\n[3/3] Tracking movement through {len(period_schedule)} periods...")

    movement_records = []

    for quarter_name, end_date_str in period_schedule:
        print(f"  [{quarter_name}] Running GLMM on cumulative data...", end=" ")

        # filter to cumulative data up to this quarter
        cumulative_df = df[
            (df[timestamp_col] < pd.Timestamp(end_date_str))
            & (df[entity_col].isin(valid_entity_list))
        ]

        if len(cumulative_df) < 100:
            print(f"⚠ Insufficient data ({len(cumulative_df)} rows)")
            continue

        # run glmm on this cumulative period
        try:
            period_results, _ = fit_priority_matrix(
                cumulative_df,
                entity_col=entity_col,
                timestamp_col=timestamp_col,
                min_observations=0,
                min_total_count=0,
                decline_window_quarters=0,
                temporal_granularity=temporal_granularity,
                vcp_p=vcp_p,
                fe_p=fe_p,
            )

            print(f"{len(period_results)} entities")

            # merge with global baseline
            for _, row in period_results.iterrows():
                entity = row[entity_col]

                if entity in global_baseline:
                    # Calculate period_quadrant from cumulative coordinates
                    # This aligns transitions with trajectory visualization
                    x, y = row["x_score"], row["y_score"]
                    if x > 0 and y > 0:
                        period_quad = "Q1"
                    elif x <= 0 and y > 0:
                        period_quad = "Q2"
                    elif x <= 0 and y <= 0:
                        period_quad = "Q3"
                    else:
                        period_quad = "Q4"
                    
                    movement_records.append(
                        {
                            "entity": entity,
                            period_col: quarter_name,
                            "cumulative_count": row["count"],
                            "period_x": row["x_score"],
                            "period_y": row["y_score"],
                            "period_quadrant": period_quad,
                            "global_quadrant": global_baseline[entity][
                                "global_quadrant"
                            ],
                            "global_x": global_baseline[entity]["global_x"],
                            "global_y": global_baseline[entity]["global_y"],
                            "count_total": global_baseline[entity]["count_total"],
                        }
                    )

        except Exception as e:
            print(f"✗ Error: {str(e)[:50]}")
            continue

    movement_df = pd.DataFrame(movement_records)

    if movement_df.empty:
        movement_df = pd.DataFrame(
            columns=[
                "entity",
                period_col,
                "period_count",
                "cumulative_count",
                "period_x",
                "period_y",
                "period_quadrant",
                "global_quadrant",
                "global_x",
                "global_y",
                "count_total",
                "x_delta",
                "y_delta",
                "quadrant_differs",
            ]
        )

    # step 4: calculate movement metrics
    print("\n[4/4] Calculating movement metrics...")

    # add period-over-period changes
    movement_df = movement_df.sort_values(["entity", period_col])

    # calculate deltas
    movement_df["x_delta"] = movement_df.groupby("entity")["period_x"].diff()
    movement_df["y_delta"] = movement_df.groupby("entity")["period_y"].diff()

    # new event count per period
    movement_df["period_count"] = movement_df.groupby("entity")[
        "cumulative_count"
    ].diff()

    # detect quadrant divergence
    movement_df["quadrant_differs"] = (
        movement_df["period_quadrant"] != movement_df["global_quadrant"]
    )

    # reorder columns for readability
    cols = [
        "entity",
        period_col,
        "period_count",
        "cumulative_count",
        "period_x",
        "period_y",
        "period_quadrant",
        "global_quadrant",
        "global_x",
        "global_y",
        "count_total",
        "x_delta",
        "y_delta",
        "quadrant_differs",
    ]
    # keep any extra columns at the end
    movement_df = movement_df[
        [c for c in cols if c in movement_df.columns]
        + [c for c in movement_df.columns if c not in cols]
    ]

    print(f"Tracked {len(movement_df)} entity-period observations")
    print(f"Entities tracked: {movement_df['entity'].nunique()}")
    print(f"Periods covered: {movement_df[period_col].nunique()}")

    divergence_count = movement_df["quadrant_differs"].sum()
    divergence_pct = (
        (divergence_count / len(movement_df) * 100) if len(movement_df) > 0 else 0
    )
    print(f"Quadrant divergences: {divergence_count} ({divergence_pct:.1f}%)")

    # metadata
    metadata = {
        "entities_tracked": movement_df["entity"].nunique()
        if not movement_df.empty
        else 0,
        "quarters_analyzed": len(period_schedule),
        "total_observations": len(movement_df),
        "divergence_rate": divergence_pct,
        "temporal_granularity": temporal_granularity,
        "quarter_schedule": period_schedule,
    }

    return movement_df, metadata


def load_or_track_movement(
    df_raw: pd.DataFrame,
    *,
    entity_name: str,
    entity_col: str,
    timestamp_col: str,
    quarters,
    min_total_count: int,
    temporal_granularity: str = "quarterly",
    output_dir: str = "results/csv",
    use_cache: bool = True,
) -> tuple[pd.DataFrame, str | None]:
    """Load latest movement CSV for entity or compute and save.

    When ``use_cache`` is True, tries to load the most recent
    ``movement-<entity_slug>-*.csv`` from ``output_dir``. If not
    found, runs tracking and saves a fresh movement CSV.
    """

    csv_path: str | None = None
    if use_cache:
        csv_path = latest_artifact_csv(
            "movement",
            entity_name,
            output_dir,
            temporal_granularity=temporal_granularity,
        )
        if csv_path:
            movement_df = pd.read_csv(csv_path)
            if temporal_granularity == "monthly":
                # New-style monthly CSVs use a friendlier ``month``
                # column on disk; normalize to ``quarter`` in-memory
                # for compatibility with existing code.
                if (
                    "month" in movement_df.columns
                    and "quarter" not in movement_df.columns
                ):
                    movement_df = movement_df.rename(columns={"month": "quarter"})

                # Legacy monthly CSVs were written with a ``quarter``
                # column. Treat that as ``month`` for users by
                # rewriting the CSV header to ``month`` while keeping
                # the in-memory schema unchanged.
                elif (
                    "quarter" in movement_df.columns
                    and "month" not in movement_df.columns
                ):
                    month_df = movement_df.rename(columns={"quarter": "month"})
                    month_df.to_csv(csv_path, index=False)
                    movement_df = month_df.rename(columns={"month": "quarter"})

            return movement_df, csv_path

    movement_df, _meta = track_cumulative_movement(
        df_raw,
        entity_col=entity_col,
        timestamp_col=timestamp_col,
        quarters=quarters,
        min_total_count=min_total_count,
        temporal_granularity=temporal_granularity,
    )

    # For monthly outputs, persist a friendlier "month" label on disk
    # while keeping the in-memory DataFrame schema unchanged.
    movement_to_save = movement_df
    if temporal_granularity == "monthly" and "quarter" in movement_df.columns:
        movement_to_save = movement_df.rename(columns={"quarter": "month"})

    csv_path = save_dataframe_to_csv(
        movement_to_save,
        artifact="movement",
        entity_name=entity_name,
        temporal_granularity=temporal_granularity,
        output_dir=output_dir,
    )

    return movement_df, csv_path
