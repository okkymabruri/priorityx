"""Data quality filters for entity analysis."""

from datetime import timedelta
import numpy as np

import pandas as pd


def filter_sparse_entities(
    df: pd.DataFrame,
    entity_col: str,
    timestamp_col: str,
    min_total_count: int = 20,
    min_observations: int = 3,
    temporal_granularity: str = "yearly",
) -> pd.DataFrame:
    """
    Filter entities with insufficient data.

    Removes entities that don't meet minimum thresholds for:
    - Total count across all time periods
    - Number of time period observations

    Args:
        df: Input pandas DataFrame
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
    df = df.copy()
    n_before = df[entity_col].nunique()

    # filter by total count
    if min_total_count > 0:
        total_counts = df.groupby(entity_col).size().reset_index(name="total_count")
        valid_entities = total_counts[total_counts["total_count"] >= min_total_count][
            entity_col
        ]
        df = df[df[entity_col].isin(valid_entities)]

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
            df["year"] = pd.to_datetime(df[timestamp_col]).dt.year
            df["quarter"] = pd.to_datetime(df[timestamp_col]).dt.quarter
            period_counts = (
                df.groupby(entity_col)
                .apply(
                    lambda x: len(x[["year", "quarter"]].drop_duplicates()),
                    include_groups=False,
                )
                .reset_index(name="n_periods")
            )
        elif temporal_granularity == "semiannual":
            df["year"] = pd.to_datetime(df[timestamp_col]).dt.year
            df["quarter"] = pd.to_datetime(df[timestamp_col]).dt.quarter
            df["semester"] = np.where(df["quarter"] <= 2, 1, 2)
            period_counts = (
                df.groupby(entity_col)
                .apply(
                    lambda x: len(x[["year", "semester"]].drop_duplicates()),
                    include_groups=False,
                )
                .reset_index(name="n_periods")
            )
        else:  # yearly
            df["year"] = pd.to_datetime(df[timestamp_col]).dt.year
            period_counts = (
                df.groupby(entity_col)["year"].nunique().reset_index(name="n_periods")
            )

        valid_entities = period_counts[period_counts["n_periods"] >= min_obs][
            entity_col
        ]
        df = df[df[entity_col].isin(valid_entities)]

    n_after = df[entity_col].nunique()
    n_filtered = n_before - n_after

    if n_filtered > 0:
        print(f"Filtered {n_filtered} sparse entities")

    return df


def filter_stale_entities(
    df: pd.DataFrame,
    entity_col: str,
    timestamp_col: str,
    decline_window_quarters: int = 6,
) -> pd.DataFrame:
    """
    Filter entities inactive for more than N quarters.

    Removes entities whose last observation is too far in the past
    relative to the dataset's most recent date. Prevents long-inactive
    entities from contaminating the model baseline.

    Args:
        df: Input pandas DataFrame
        entity_col: Column name for entity identifier
        timestamp_col: Column name for timestamp (datetime type)
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

    df = df.copy()
    df[timestamp_col] = pd.to_datetime(df[timestamp_col])

    # find last observation per entity
    last_observation = (
        df.groupby(entity_col)[timestamp_col].max().reset_index(name="last_date")
    )

    # get dataset max date
    dataset_max_date = df[timestamp_col].max()

    # calculate cutoff date
    decline_cutoff = dataset_max_date - timedelta(
        days=decline_window_quarters * 91  # ~91 days per quarter
    )

    n_before = df[entity_col].nunique()

    # identify stale entities
    stale_entities = last_observation[last_observation["last_date"] < decline_cutoff][
        entity_col
    ]

    # filter them out
    df = df[~df[entity_col].isin(stale_entities)]

    n_after = df[entity_col].nunique()
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
    valid_quarters = quarter_counts[quarter_counts >= min_entities_per_quarter].index

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
