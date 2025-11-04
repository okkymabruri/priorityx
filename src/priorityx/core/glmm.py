"""GLMM estimation for entity prioritization using Poisson mixed models."""

from typing import Dict, Literal, Optional, Tuple

import pandas as pd
import polars as pl
from statsmodels.genmod.bayes_mixed_glm import PoissonBayesMixedGLM

# default priors (validated on regulatory data)
DEFAULT_VCP_P = 3.5  # prior scale for random effects (higher = less shrinkage)
DEFAULT_FE_P = 3.0  # prior scale for fixed effects


def _extract_random_effects(
    glmm_model, glmm_result
) -> tuple[dict[str, float], dict[str, float]]:
    """Extract random intercepts and slopes from statsmodels result."""
    intercepts: dict[str, float] = {}
    slopes: dict[str, float] = {}
    for name, value in zip(glmm_model.vc_names, glmm_result.vc_mean):
        entity = name.split("[", 1)[1].split("]", 1)[0]
        val = float(value)
        if ":time" in name:
            slopes[entity] = val
        else:
            intercepts[entity] = val
    return intercepts, slopes


def fit_priority_matrix(
    df: pl.LazyFrame | pl.DataFrame,
    entity_col: str,
    timestamp_col: str,
    count_col: Optional[str] = None,
    date_filter: Optional[str] = None,
    min_observations: int = 3,
    min_total_count: int = 0,
    decline_window_quarters: int = 6,
    temporal_granularity: Literal["yearly", "quarterly", "semiannual"] = "yearly",
    vcp_p: float = DEFAULT_VCP_P,
    fe_p: float = DEFAULT_FE_P,
) -> Tuple[pd.DataFrame, Dict]:
    """
    Fit Poisson GLMM to classify entities into priority quadrants.

    Args:
        df: Input DataFrame
        entity_col: Entity identifier column
        timestamp_col: Date column
        count_col: Count metric column (defaults to row count)
        date_filter: Date filter (e.g., "< 2025-01-01")
        min_observations: Minimum time periods required
        min_total_count: Minimum total count threshold
        decline_window_quarters: Filter entities inactive >N quarters
        temporal_granularity: Time aggregation level
        vcp_p: Random effects prior scale
        fe_p: Fixed effects prior scale

    Returns:
        Tuple of (results DataFrame, statistics dict)
    """
    # ensure dataframe
    if isinstance(df, pl.LazyFrame):
        df = df.collect()

    # ensure timestamp column is Date type
    df = df.with_columns(pl.col(timestamp_col).cast(pl.Date))

    # apply date filter if specified
    if date_filter:
        date_filter_clean = date_filter.strip()

        # parse filter operators
        if date_filter_clean.startswith("<="):
            date_value = date_filter_clean[2:].strip()
            df = df.filter(
                pl.col(timestamp_col) <= pl.lit(date_value).cast(pl.Date)
            )
        elif date_filter_clean.startswith(">="):
            date_value = date_filter_clean[2:].strip()
            df = df.filter(
                pl.col(timestamp_col) >= pl.lit(date_value).cast(pl.Date)
            )
        elif date_filter_clean.startswith("<"):
            date_value = date_filter_clean[1:].strip()
            df = df.filter(
                pl.col(timestamp_col) < pl.lit(date_value).cast(pl.Date)
            )
        elif date_filter_clean.startswith(">"):
            date_value = date_filter_clean[1:].strip()
            df = df.filter(
                pl.col(timestamp_col) > pl.lit(date_value).cast(pl.Date)
            )
        else:
            # assume date only (use < for backward compatibility)
            df = df.filter(
                pl.col(timestamp_col) < pl.lit(date_filter).cast(pl.Date)
            )

    # filter by minimum total count if specified
    n_before_volume_filter = df.select(entity_col).n_unique()
    if min_total_count > 0:
        total_counts = df.group_by(entity_col).agg(pl.len().alias("total_count"))
        valid_entities = total_counts.filter(
            pl.col("total_count") >= min_total_count
        )[entity_col]
        df = df.filter(pl.col(entity_col).is_in(valid_entities))
        n_after_volume_filter = df.select(entity_col).n_unique()
        n_filtered_volume = n_before_volume_filter - n_after_volume_filter
        if n_filtered_volume > 0:
            print(
                f"  Filtered {n_filtered_volume} entities (<{min_total_count} total count)"
            )

    # filter stale entities (decline window)
    if decline_window_quarters > 0 and temporal_granularity == "quarterly":
        last_observation = df.group_by(entity_col).agg(
            pl.col(timestamp_col).max().alias("last_date")
        )

        from datetime import timedelta

        # use max date in dataset for historical analysis
        dataset_max_datetime = df.select(pl.col(timestamp_col).max()).item()
        dataset_max_date = (
            dataset_max_datetime.date()
            if hasattr(dataset_max_datetime, "date")
            else dataset_max_datetime
        )
        decline_cutoff = dataset_max_date - timedelta(
            days=decline_window_quarters * 91  # ~91 days per quarter
        )

        n_before_decline_filter = df.select(entity_col).n_unique()
        stale_entities = last_observation.filter(
            pl.col("last_date").cast(pl.Date) < pl.lit(decline_cutoff).cast(pl.Date)
        )[entity_col]

        df = df.filter(~pl.col(entity_col).is_in(stale_entities))
        n_after_decline_filter = df.select(entity_col).n_unique()
        n_filtered_stale = n_before_decline_filter - n_after_decline_filter

        if n_filtered_stale > 0:
            print(
                f"  Filtered {n_filtered_stale} entities (inactive >{decline_window_quarters}Q)"
            )

    # auto-adjust min_observations for temporal granularity
    if min_observations == 3 and temporal_granularity == "quarterly":
        min_observations = 8  # 2 years quarterly
    elif min_observations == 3 and temporal_granularity == "semiannual":
        min_observations = 4  # 2 years semiannual

    # prepare aggregation based on temporal granularity
    if temporal_granularity == "quarterly":
        df = df.with_columns(
            [
                pl.col(timestamp_col).dt.year().alias("year"),
                pl.col(timestamp_col).dt.quarter().alias("quarter"),
            ]
        )

        if count_col:
            df_prepared = (
                df.group_by(["year", "quarter", entity_col])
                .agg(pl.col(count_col).sum().alias("count"))
                .sort(["year", "quarter", entity_col])
            )
        else:
            df_prepared = (
                df.group_by(["year", "quarter", entity_col])
                .agg(pl.len().alias("count"))
                .sort(["year", "quarter", entity_col])
            )

    elif temporal_granularity == "semiannual":
        df = df.with_columns(
            [
                pl.col(timestamp_col).dt.year().alias("year"),
                pl.col(timestamp_col).dt.quarter().alias("quarter"),
            ]
        ).with_columns(
            # semester: Q1-Q2 = 1, Q3-Q4 = 2
            pl.when(pl.col("quarter") <= 2)
            .then(pl.lit(1))
            .otherwise(pl.lit(2))
            .alias("semester")
        )

        if count_col:
            df_prepared = (
                df.group_by(["year", "semester", entity_col])
                .agg(pl.col(count_col).sum().alias("count"))
                .sort(["year", "semester", entity_col])
            )
        else:
            df_prepared = (
                df.group_by(["year", "semester", entity_col])
                .agg(pl.len().alias("count"))
                .sort(["year", "semester", entity_col])
            )

    else:  # yearly
        df = df.with_columns(pl.col(timestamp_col).dt.year().alias("year"))

        if count_col:
            df_prepared = (
                df.group_by(["year", entity_col])
                .agg(pl.col(count_col).sum().alias("count"))
                .sort(["year", entity_col])
            )
        else:
            df_prepared = (
                df.group_by(["year", entity_col])
                .agg(pl.len().alias("count"))
                .sort(["year", entity_col])
            )

    # filter entities with sufficient observations
    if min_observations > 0:
        entity_counts = df_prepared.group_by(entity_col).agg(
            pl.len().alias("n_periods")
        )
        valid_entities = entity_counts.filter(
            pl.col("n_periods") >= min_observations
        )[entity_col]
        df_prepared = df_prepared.filter(pl.col(entity_col).is_in(valid_entities))

    # ensure count is integer
    df_prepared = df_prepared.with_columns(pl.col("count").cast(pl.Int64))

    # create time variable based on temporal granularity
    if temporal_granularity == "quarterly":
        # continuous quarterly time: year + (quarter-1)/4
        df_prepared = df_prepared.with_columns(
            (pl.col("year") + (pl.col("quarter") - 1) / 4).alias("time_continuous")
        )

        # center for numerical stability
        mean_time = df_prepared["time_continuous"].mean()
        df_prepared = df_prepared.with_columns(
            (pl.col("time_continuous") - mean_time).alias("time")
        )

    elif temporal_granularity == "semiannual":
        # continuous semiannual time: year + (semester-1)/2
        df_prepared = df_prepared.with_columns(
            (pl.col("year") + (pl.col("semester") - 1) / 2).alias("time_continuous")
        )

        # center for numerical stability
        mean_time = df_prepared["time_continuous"].mean()
        df_prepared = df_prepared.with_columns(
            (pl.col("time_continuous") - mean_time).alias("time")
        )

    else:  # yearly
        # center year for numerical stability
        mean_year = df_prepared["year"].mean()
        df_prepared = df_prepared.with_columns(
            (pl.col("year") - mean_year).alias("time")
        )

    # ensure categorical type for entity
    df_prepared = df_prepared.with_columns(pl.col(entity_col).cast(pl.Categorical))

    # make period categorical for seasonal effects
    if temporal_granularity == "quarterly":
        df_prepared = df_prepared.with_columns(pl.col("quarter").cast(pl.Categorical))
    elif temporal_granularity == "semiannual":
        df_prepared = df_prepared.with_columns(pl.col("semester").cast(pl.Categorical))

    # ensure positive counts for poisson
    df_prepared = df_prepared.filter(pl.col("count") > 0)

    # convert to pandas for statsmodels
    df_pandas = df_prepared.to_pandas()
    df_pandas["time"] = df_pandas["time"].astype(float)
    df_pandas[entity_col] = df_pandas[entity_col].astype("category")

    # build fixed-effect formula with seasonal dummies
    formula = "count ~ time"
    if temporal_granularity == "quarterly":
        df_pandas["quarter"] = df_pandas["quarter"].astype("category")
        formula += " + C(quarter)"
    elif temporal_granularity == "semiannual":
        df_pandas["semester"] = df_pandas["semester"].astype("category")
        formula += " + C(semester)"

    # random effects: intercept + slope per entity
    random_formulas = {
        "re_int": f"0 + C({entity_col})",
        "re_slope": f"0 + C({entity_col}):time",
    }

    # fit poisson bayesian mixed model
    glmm_model = PoissonBayesMixedGLM.from_formula(
        formula,
        random_formulas,
        df_pandas,
        vcp_p=vcp_p,
        fe_p=fe_p,
    )

    # use variational bayes (returns posterior mean)
    # avoids boundary convergence issues vs map
    glmm_result = glmm_model.fit_vb()

    # extract random effects
    intercepts_dict, slopes_dict = _extract_random_effects(glmm_model, glmm_result)

    # convert to lists for dataframe
    entities = list(intercepts_dict.keys())
    intercepts = [intercepts_dict[ent] for ent in entities]
    slopes = [slopes_dict[ent] for ent in entities]

    # create results dataframe
    df_random_effects = pl.DataFrame(
        {"entity": entities, "Random_Intercept": intercepts, "Random_Slope": slopes}
    )

    # calculate totals from original filtered data
    df_totals = (
        df.group_by(entity_col)
        .agg(pl.len().alias("count"))
        .sort(entity_col)
    )

    # convert to pandas for merging
    df_random_effects_pd = df_random_effects.to_pandas()
    df_totals_pd = df_totals.to_pandas()

    # merge
    results_df = df_random_effects_pd.merge(
        df_totals_pd, left_on="entity", right_on=entity_col, how="left"
    )

    # import quadrant classifier
    from .quadrants import classify_quadrant

    # add quadrant classification
    results_df["quadrant"] = results_df.apply(
        lambda row: classify_quadrant(
            row["Random_Intercept"],
            row["Random_Slope"],
            count=row.get("count"),
            min_q1_count=50,  # crisis threshold
        ),
        axis=1,
    )

    # model statistics
    model_stats = {
        "n_entities": len(results_df),
        "n_observations": len(df_prepared),
        "method": "VB",
        "vcp_p": vcp_p,
        "fe_p": fe_p,
        "temporal_granularity": temporal_granularity,
    }

    # add fixed effects if available
    try:
        if hasattr(glmm_result, "params"):
            params = glmm_result.params
            model_stats["fixed_intercept"] = float(
                params.get("Intercept", params.get("(Intercept)", 0.0))
            )
            model_stats["fixed_slope"] = float(params.get("time", 0.0))
        else:
            model_stats["fixed_intercept"] = None
            model_stats["fixed_slope"] = None
    except Exception:
        model_stats["fixed_intercept"] = None
        model_stats["fixed_slope"] = None

    return results_df, model_stats
