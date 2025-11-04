"""Data quality filters for entity analysis."""

from datetime import timedelta

import pandas as pd
import polars as pl


def filter_sparse_entities(
    df: pl.DataFrame,
    entity_col: str,
    timestamp_col: str,
    min_total_count: int = 20,
    min_observations: int = 3,
    temporal_granularity: str = "yearly",
) -> pl.DataFrame:
    """
    Filter entities with insufficient data.

    Removes entities that don't meet minimum thresholds for:
    - Total count across all time periods
    - Number of time period observations

    Args:
        df: Input polars DataFrame
        entity_col: Column name for entity identifier
        timestamp_col: Column name for timestamp
        min_total_count: Minimum total count (default: 20)
        min_observations: Minimum time periods (default: 3)
                         Auto-adjusts for temporal_granularity
        temporal_granularity: 'yearly', 'quarterly', or 'semiannual'

    Returns:
        Filtered DataFrame with only entities meeting thresholds

    Examples:
        >>> df_filtered = filter_sparse_entities(
        ...     df, entity_col="service", timestamp_col="date",
        ...     min_total_count=50, min_observations=8
        ... )
    """
    n_before = df.select(entity_col).n_unique()

    # filter by total count
    if min_total_count > 0:
        total_counts = df.group_by(entity_col).agg(pl.len().alias("total_count"))
        valid_entities = total_counts.filter(
            pl.col("total_count") >= min_total_count
        )[entity_col]
        df = df.filter(pl.col(entity_col).is_in(valid_entities))

    # filter by observations (time periods)
    if min_observations > 0:
        # auto-adjust for granularity
        min_obs = min_observations
        if min_obs == 3 and temporal_granularity == "quarterly":
            min_obs = 8  # 2 years
        elif min_obs == 3 and temporal_granularity == "semiannual":
            min_obs = 4  # 2 years

        # count unique periods per entity
        if temporal_granularity == "quarterly":
            df_temp = df.with_columns(
                [
                    pl.col(timestamp_col).dt.year().alias("year"),
                    pl.col(timestamp_col).dt.quarter().alias("quarter"),
                ]
            )
            period_counts = df_temp.group_by(entity_col).agg(
                pl.struct(["year", "quarter"]).n_unique().alias("n_periods")
            )
        elif temporal_granularity == "semiannual":
            df_temp = df.with_columns(
                [
                    pl.col(timestamp_col).dt.year().alias("year"),
                    pl.col(timestamp_col).dt.quarter().alias("quarter"),
                ]
            ).with_columns(
                pl.when(pl.col("quarter") <= 2)
                .then(pl.lit(1))
                .otherwise(pl.lit(2))
                .alias("semester")
            )
            period_counts = df_temp.group_by(entity_col).agg(
                pl.struct(["year", "semester"]).n_unique().alias("n_periods")
            )
        else:  # yearly
            df_temp = df.with_columns(pl.col(timestamp_col).dt.year().alias("year"))
            period_counts = df_temp.group_by(entity_col).agg(
                pl.col("year").n_unique().alias("n_periods")
            )

        valid_entities = period_counts.filter(
            pl.col("n_periods") >= min_obs
        )[entity_col]
        df = df.filter(pl.col(entity_col).is_in(valid_entities))

    n_after = df.select(entity_col).n_unique()
    n_filtered = n_before - n_after

    if n_filtered > 0:
        print(f"Filtered {n_filtered} sparse entities")

    return df


def filter_stale_entities(
    df: pl.DataFrame,
    entity_col: str,
    timestamp_col: str,
    decline_window_quarters: int = 6,
) -> pl.DataFrame:
    """
    Filter entities inactive for more than N quarters.

    Removes entities whose last observation is too far in the past
    relative to the dataset's most recent date. Prevents long-inactive
    entities from contaminating the model baseline.

    Args:
        df: Input polars DataFrame
        entity_col: Column name for entity identifier
        timestamp_col: Column name for timestamp (Date type)
        decline_window_quarters: Maximum quarters since last observation (default: 6)

    Returns:
        Filtered DataFrame excluding stale entities

    Examples:
        >>> df_active = filter_stale_entities(
        ...     df, entity_col="service", timestamp_col="date",
        ...     decline_window_quarters=6
        ... )
    """
    if decline_window_quarters <= 0:
        return df

    # find last observation per entity
    last_observation = df.group_by(entity_col).agg(
        pl.col(timestamp_col).max().alias("last_date")
    )

    # get dataset max date
    dataset_max_datetime = df.select(pl.col(timestamp_col).max()).item()
    dataset_max_date = (
        dataset_max_datetime.date()
        if hasattr(dataset_max_datetime, "date")
        else dataset_max_datetime
    )

    # calculate cutoff date
    decline_cutoff = dataset_max_date - timedelta(
        days=decline_window_quarters * 91  # ~91 days per quarter
    )

    n_before = df.select(entity_col).n_unique()

    # identify stale entities
    stale_entities = last_observation.filter(
        pl.col("last_date").cast(pl.Date) < pl.lit(decline_cutoff).cast(pl.Date)
    )[entity_col]

    # filter them out
    df = df.filter(~pl.col(entity_col).is_in(stale_entities))

    n_after = df.select(entity_col).n_unique()
    n_filtered = n_before - n_after

    if n_filtered > 0:
        print(
            f"  Filtered {n_filtered} stale entities (inactive >{decline_window_quarters}Q)"
        )

    return df


def filter_sparse_quarters(
    movement_df: pd.DataFrame,
    quarter_col: str = "quarter",
    entity_col: str = "entity",
    min_entities_per_quarter: int = 3,
) -> pd.DataFrame:
    """
    Remove quarters with too few entity observations.

    Prevents unstable GLMM estimates from sparse time periods.
    Useful for cumulative movement tracking where early quarters
    may have insufficient entities.

    Args:
        movement_df: Pandas DataFrame with movement tracking data
        quarter_col: Column name for quarter identifier (default: "quarter")
        entity_col: Column name for entity identifier (default: "entity")
        min_entities_per_quarter: Minimum entities required (default: 3)

    Returns:
        Filtered DataFrame with only quarters meeting threshold

    Examples:
        >>> movement_clean = filter_sparse_quarters(
        ...     movement_df, min_entities_per_quarter=5
        ... )
    """
    # count unique entities per quarter
    quarter_counts = movement_df.groupby(quarter_col)[entity_col].nunique()

    # identify valid quarters
    valid_quarters = quarter_counts[
        quarter_counts >= min_entities_per_quarter
    ].index

    # filter
    filtered_df = movement_df[movement_df[quarter_col].isin(valid_quarters)]

    n_dropped = len(movement_df) - len(filtered_df)
    n_quarters_dropped = len(quarter_counts) - len(valid_quarters)

    if n_dropped > 0:
        print(
            f"  Filtered {n_quarters_dropped} sparse quarters "
            f"({n_dropped} observations, <{min_entities_per_quarter} entities/quarter)"
        )

    return filtered_df
