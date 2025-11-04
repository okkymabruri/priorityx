"""Cumulative movement tracking through priority quadrants."""

from datetime import timedelta
from typing import Optional, Sequence, Union

import pandas as pd
import polars as pl


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


def _build_quarter_schedule_from_range(
    start_date: str, end_date: str
) -> list[tuple[str, str]]:
    """
    Build quarter schedule from date range.

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


def _build_default_quarter_schedule(
    df: pl.DataFrame, timestamp_col: str
) -> list[tuple[str, str]]:
    """
    Create default quarter schedule spanning the dataset.

    Args:
        df: Input polars DataFrame
        timestamp_col: Column name for timestamp

    Returns:
        List of (label, exclusive_end_date) tuples
    """
    if timestamp_col not in df.columns or df.height == 0:
        return []

    min_date = df[timestamp_col].min()
    max_date = df[timestamp_col].max()

    if min_date is None or max_date is None:
        return []

    start_ts = pd.Timestamp(min_date).to_period("Q").to_timestamp(how="start")
    # exclusive boundary: first day of quarter following max_date
    max_quarter_start = pd.Timestamp(max_date).to_period("Q").to_timestamp(how="start")
    end_ts = _next_quarter_start(max_quarter_start)

    return _build_quarter_schedule_from_range(
        start_ts.strftime("%Y-%m-%d"), end_ts.strftime("%Y-%m-%d")
    )


def normalize_quarter_schedule(
    quarters: Optional[Sequence[Union[tuple[str, str], str]]],
    df: pl.DataFrame,
    timestamp_col: str,
) -> list[tuple[str, str]]:
    """
    Normalize quarter schedule to standard format.

    Accepts three input formats:
    1. Explicit schedule: [("2024-Q2", "2024-07-01"), ...]
    2. Date range: ["2024-01-01", "2025-10-01"] (auto-generates quarters)
    3. None: Auto-detect from data

    Args:
        quarters: Quarter specification (see formats above)
        df: Input polars DataFrame
        timestamp_col: Column name for timestamp

    Returns:
        List of (quarter_label, exclusive_end_date) tuples

    Examples:
        >>> # explicit schedule
        >>> normalize_quarter_schedule(
        ...     [("2024-Q1", "2024-04-01"), ("2024-Q2", "2024-07-01")],
        ...     df, "date"
        ... )

        >>> # date range (auto-generates quarters)
        >>> normalize_quarter_schedule(
        ...     ["2024-01-01", "2025-01-01"], df, "date"
        ... )

        >>> # auto-detect from data
        >>> normalize_quarter_schedule(None, df, "date")
    """
    if quarters is None:
        return _build_default_quarter_schedule(df, timestamp_col)

    if len(quarters) == 0:
        return []

    # check first element type
    quarters[0]

    # date range format: ["2024-01-01", "2025-10-01"]
    if len(quarters) == 2 and all(isinstance(q, str) for q in quarters):
        return _build_quarter_schedule_from_range(quarters[0], quarters[1])

    # explicit schedule format: [("2024-Q2", "2024-07-01"), ...]
    normalized_schedule: list[tuple[str, str]] = []
    for entry in quarters:
        if not isinstance(entry, tuple) or len(entry) != 2:
            raise ValueError(
                "quarters must be a list of (label, cutoff_date) tuples "
                "or two quarter boundary strings"
            )
        label, cutoff = entry
        normalized_schedule.append((label, cutoff))

    return normalized_schedule


def track_cumulative_movement(
    df: pl.DataFrame | pl.LazyFrame,
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
        df: Input polars DataFrame or LazyFrame
        entity_col: Column name for entity identifier
        timestamp_col: Column name for timestamp (Date type)
        quarters: Quarter specification (see normalize_quarter_schedule)
        min_total_count: Minimum total count for inclusion (default: 20)
        decline_window_quarters: Max quarters after last observation (default: 6)
        temporal_granularity: Time granularity for GLMM ('quarterly', 'yearly', 'semiannual')
        vcp_p: Prior scale for random effects (default: 3.5)
        fe_p: Prior scale for fixed effects (default: 3.0)

    Returns:
        Tuple of (movement_df, metadata_dict)
        - movement_df: Quarter-by-quarter tracking with columns:
          [entity, quarter, count_to_date, period_x, period_y, period_quadrant,
           global_quadrant, global_x, global_y, count_total, x_delta, y_delta, volume_delta]
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
    # ensure dataframe
    if isinstance(df, pl.LazyFrame):
        df = df.collect()

    # normalize quarter schedule
    quarter_schedule = normalize_quarter_schedule(quarters, df, timestamp_col)

    if len(quarter_schedule) == 0:
        print("Warning: No quarter boundaries available for cumulative tracking")
        empty_df = pd.DataFrame(
            columns=[
                "entity",
                "quarter",
                "count_to_date",
                "period_x",
                "period_y",
                "period_quadrant",
                "global_quadrant",
                "global_x",
                "global_y",
                "count_total",
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
            "global_x": row["Random_Intercept"],
            "global_y": row["Random_Slope"],
            "count_total": row["count"],
        }

    # step 2: determine valid entities at analysis endpoint
    print("\n[2/3] Determining valid entities at analysis endpoint...")

    # get endpoint (last quarter)
    final_quarter_name, final_quarter_date = quarter_schedule[-1]
    print(f"Analysis endpoint: {final_quarter_name} ({final_quarter_date})")

    # calculate valid entities based on cumulative totals up to endpoint
    endpoint_pl = pl.lit(final_quarter_date).str.to_date()
    cumulative_up_to_endpoint = df.filter(pl.col(timestamp_col) < endpoint_pl)

    # apply filters in same order as fit_priority_matrix for consistency

    # step 1: filter by min_total_count
    endpoint_totals = cumulative_up_to_endpoint.group_by(entity_col).agg(
        pl.len().alias("total")
    )
    entities_above_threshold = endpoint_totals.filter(
        pl.col("total") >= min_total_count
    )[entity_col]
    cumulative_up_to_endpoint = cumulative_up_to_endpoint.filter(
        pl.col(entity_col).is_in(entities_above_threshold)
    )

    # step 2: apply decline_window filter
    if decline_window_quarters > 0:
        dataset_max_datetime = cumulative_up_to_endpoint.select(
            pl.col(timestamp_col).max()
        ).item()
        dataset_max_date = (
            dataset_max_datetime.date()
            if hasattr(dataset_max_datetime, "date")
            else dataset_max_datetime
        )
        decline_cutoff = dataset_max_date - timedelta(
            days=decline_window_quarters * 91
        )

        last_observation_at_endpoint = cumulative_up_to_endpoint.group_by(
            entity_col
        ).agg(pl.col(timestamp_col).max().alias("last_date"))
        stale_entities_at_endpoint = last_observation_at_endpoint.filter(
            pl.col("last_date").cast(pl.Date) < pl.lit(decline_cutoff).cast(pl.Date)
        )[entity_col]
        cumulative_up_to_endpoint = cumulative_up_to_endpoint.filter(
            ~pl.col(entity_col).is_in(stale_entities_at_endpoint)
        )
        n_stale = len(stale_entities_at_endpoint)
        if n_stale > 0:
            print(
                f"  Filtered {n_stale} stale entities at endpoint "
                f"(inactive >{decline_window_quarters}Q)"
            )

    # get final entity list after filters
    valid_entity_list = (
        cumulative_up_to_endpoint.select(entity_col).unique().to_series().to_list()
    )

    n_valid_at_endpoint = len(valid_entity_list)
    print(
        f"  Valid entities (≥{min_total_count} count by {final_quarter_name}): "
        f"{n_valid_at_endpoint}"
    )

    # step 3: track movement through quarters
    print(f"\n[3/3] Tracking movement through {len(quarter_schedule)} quarters...")

    movement_records = []

    for quarter_name, end_date_str in quarter_schedule:
        print(f"  [{quarter_name}] Running GLMM on cumulative data...", end=" ")

        # filter to cumulative data up to this quarter
        end_pl = pl.lit(end_date_str).str.to_date()
        cumulative_df = df.filter(
            (pl.col(timestamp_col) < end_pl)
            & (pl.col(entity_col).is_in(valid_entity_list))
        )

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
                    movement_records.append(
                        {
                            "entity": entity,
                            "quarter": quarter_name,
                            "count_to_date": row["count"],
                            "period_x": row["Random_Intercept"],
                            "period_y": row["Random_Slope"],
                            "period_quadrant": row["quadrant"],
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
                "quarter",
                "count_to_date",
                "period_x",
                "period_y",
                "period_quadrant",
                "global_quadrant",
                "global_x",
                "global_y",
                "count_total",
                "x_delta",
                "y_delta",
                "volume_delta",
            ]
        )

    # step 4: calculate movement metrics
    print("\n[4/4] Calculating movement metrics...")

    # add quarter-over-quarter changes
    movement_df = movement_df.sort_values(["entity", "quarter"])

    # calculate deltas
    movement_df["x_delta"] = movement_df.groupby("entity")["period_x"].diff()
    movement_df["y_delta"] = movement_df.groupby("entity")["period_y"].diff()
    movement_df["volume_delta"] = movement_df.groupby("entity")[
        "count_to_date"
    ].diff()

    # detect quadrant divergence
    movement_df["quadrant_differs"] = (
        movement_df["period_quadrant"] != movement_df["global_quadrant"]
    )

    print(f"Tracked {len(movement_df)} entity-quarter observations")
    print(f"Entities tracked: {movement_df['entity'].nunique()}")
    print(f"Periods covered: {movement_df['quarter'].nunique()}")

    divergence_count = movement_df["quadrant_differs"].sum()
    divergence_pct = (
        (divergence_count / len(movement_df) * 100) if len(movement_df) > 0 else 0
    )
    print(f"Quadrant divergences: {divergence_count} ({divergence_pct:.1f}%)")

    # metadata
    metadata = {
        "entities_tracked": movement_df["entity"].nunique() if not movement_df.empty else 0,
        "quarters_analyzed": len(quarter_schedule),
        "total_observations": len(movement_df),
        "divergence_rate": divergence_pct,
        "temporal_granularity": temporal_granularity,
        "quarter_schedule": quarter_schedule,
    }

    return movement_df, metadata
