"""GLMM estimation for entity prioritization using Poisson mixed models."""

from typing import Dict, Literal, Optional, Tuple
from datetime import timedelta
import os
import numpy as np

import pandas as pd
from statsmodels.genmod.bayes_mixed_glm import PoissonBayesMixedGLM

# default priors (validated on regulatory data)
DEFAULT_VCP_P = 3.5  # prior scale for random effects (higher = less shrinkage)
DEFAULT_FE_P = 3.0  # prior scale for fixed effects

_ENV_VAR_NAME = "PRIORITYX_GLMM_SEED"
_GLMM_RANDOM_SEED: Optional[int] = None
_GLMM_SEED_APPLIED = False

_env_seed = os.getenv(_ENV_VAR_NAME)
if _env_seed is not None:
    try:
        _GLMM_RANDOM_SEED = int(_env_seed)
    except ValueError:
        _GLMM_RANDOM_SEED = None


def set_glmm_random_seed(seed: Optional[int]) -> None:
    """Configure deterministic seeding for GLMM estimations."""

    global _GLMM_RANDOM_SEED, _GLMM_SEED_APPLIED
    _GLMM_RANDOM_SEED = seed
    _GLMM_SEED_APPLIED = False


def _apply_random_seed() -> None:
    """Apply configured random seed exactly once per process."""

    global _GLMM_SEED_APPLIED
    if _GLMM_SEED_APPLIED:
        return
    if _GLMM_RANDOM_SEED is not None:
        np.random.seed(_GLMM_RANDOM_SEED)
    _GLMM_SEED_APPLIED = True


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
    df: pd.DataFrame,
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
    # create copy to avoid modifying original
    df = df.copy()

    # ensure timestamp column is datetime
    df[timestamp_col] = pd.to_datetime(df[timestamp_col])

    # apply date filter if specified
    if date_filter:
        date_filter_clean = date_filter.strip()

        # parse filter operators
        if date_filter_clean.startswith("<="):
            date_value = pd.Timestamp(date_filter_clean[2:].strip())
            df = df[df[timestamp_col] <= date_value]
        elif date_filter_clean.startswith(">="):
            date_value = pd.Timestamp(date_filter_clean[2:].strip())
            df = df[df[timestamp_col] >= date_value]
        elif date_filter_clean.startswith("<"):
            date_value = pd.Timestamp(date_filter_clean[1:].strip())
            df = df[df[timestamp_col] < date_value]
        elif date_filter_clean.startswith(">"):
            date_value = pd.Timestamp(date_filter_clean[1:].strip())
            df = df[df[timestamp_col] > date_value]
        else:
            # assume date only (use < for backward compatibility)
            date_value = pd.Timestamp(date_filter)
            df = df[df[timestamp_col] < date_value]

    # filter by minimum total count if specified
    n_before_volume_filter = df[entity_col].nunique()
    if min_total_count > 0:
        total_counts = df.groupby(entity_col).size().reset_index(name="total_count")
        valid_entities = total_counts[total_counts["total_count"] >= min_total_count][
            entity_col
        ]
        df = df[df[entity_col].isin(valid_entities)]
        n_after_volume_filter = df[entity_col].nunique()
        n_filtered_volume = n_before_volume_filter - n_after_volume_filter
        if n_filtered_volume > 0:
            print(
                f"  Filtered {n_filtered_volume} entities (<{min_total_count} total count)"
            )

    # filter stale entities (decline window)
    if decline_window_quarters > 0 and temporal_granularity == "quarterly":
        last_observation = (
            df.groupby(entity_col)[timestamp_col].max().reset_index(name="last_date")
        )

        # use max date in dataset for historical analysis
        dataset_max_date = df[timestamp_col].max()
        decline_cutoff = dataset_max_date - timedelta(
            days=decline_window_quarters * 91  # ~91 days per quarter
        )

        n_before_decline_filter = df[entity_col].nunique()
        stale_entities = last_observation[
            last_observation["last_date"] < decline_cutoff
        ][entity_col]

        df = df[~df[entity_col].isin(stale_entities)]
        n_after_decline_filter = df[entity_col].nunique()
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
        df["year"] = df[timestamp_col].dt.year
        df["quarter"] = df[timestamp_col].dt.quarter

        if count_col:
            df_prepared = (
                df.groupby(["year", "quarter", entity_col])[count_col]
                .sum()
                .reset_index(name="count")
                .sort_values(["year", "quarter", entity_col])
            )
        else:
            df_prepared = (
                df.groupby(["year", "quarter", entity_col])
                .size()
                .reset_index(name="count")
                .sort_values(["year", "quarter", entity_col])
            )

    elif temporal_granularity == "semiannual":
        df["year"] = df[timestamp_col].dt.year
        df["quarter"] = df[timestamp_col].dt.quarter
        # semester: Q1-Q2 = 1, Q3-Q4 = 2
        df["semester"] = np.where(df["quarter"] <= 2, 1, 2)

        if count_col:
            df_prepared = (
                df.groupby(["year", "semester", entity_col])[count_col]
                .sum()
                .reset_index(name="count")
                .sort_values(["year", "semester", entity_col])
            )
        else:
            df_prepared = (
                df.groupby(["year", "semester", entity_col])
                .size()
                .reset_index(name="count")
                .sort_values(["year", "semester", entity_col])
            )

    else:  # yearly
        df["year"] = df[timestamp_col].dt.year

        if count_col:
            df_prepared = (
                df.groupby(["year", entity_col])[count_col]
                .sum()
                .reset_index(name="count")
                .sort_values(["year", entity_col])
            )
        else:
            df_prepared = (
                df.groupby(["year", entity_col])
                .size()
                .reset_index(name="count")
                .sort_values(["year", entity_col])
            )

    # filter entities with sufficient observations
    if min_observations > 0:
        entity_counts = (
            df_prepared.groupby(entity_col).size().reset_index(name="n_periods")
        )
        valid_entities = entity_counts[entity_counts["n_periods"] >= min_observations][
            entity_col
        ]
        df_prepared = df_prepared[df_prepared[entity_col].isin(valid_entities)]

    # ensure count is integer
    df_prepared["count"] = df_prepared["count"].astype(np.int64)

    # create time variable based on temporal granularity
    if temporal_granularity == "quarterly":
        # continuous quarterly time: year + (quarter-1)/4
        df_prepared["time_continuous"] = (
            df_prepared["year"] + (df_prepared["quarter"] - 1) / 4
        )

        # center for numerical stability
        mean_time = df_prepared["time_continuous"].mean()
        df_prepared["time"] = df_prepared["time_continuous"] - mean_time

    elif temporal_granularity == "semiannual":
        # continuous semiannual time: year + (semester-1)/2
        df_prepared["time_continuous"] = (
            df_prepared["year"] + (df_prepared["semester"] - 1) / 2
        )

        # center for numerical stability
        mean_time = df_prepared["time_continuous"].mean()
        df_prepared["time"] = df_prepared["time_continuous"] - mean_time

    else:  # yearly
        # center year for numerical stability
        mean_year = df_prepared["year"].mean()
        df_prepared["time"] = df_prepared["year"] - mean_year

    # ensure categorical type for entity
    df_prepared[entity_col] = df_prepared[entity_col].astype("category")

    # make period categorical for seasonal effects
    if temporal_granularity == "quarterly":
        df_prepared["quarter"] = df_prepared["quarter"].astype("category")
    elif temporal_granularity == "semiannual":
        df_prepared["semester"] = df_prepared["semester"].astype("category")

    # ensure positive counts for poisson
    df_prepared = df_prepared[df_prepared["count"] > 0]

    # prepare for statsmodels
    df_prepared["time"] = df_prepared["time"].astype(float)

    # build fixed-effect formula with seasonal dummies
    formula = "count ~ time"

    # only add seasonal effects if multi-year data (avoid multicollinearity in single-year)
    n_years = df_prepared["year"].nunique()
    if temporal_granularity == "quarterly" and n_years >= 2:
        formula += " + C(quarter)"
    elif temporal_granularity == "semiannual" and n_years >= 2:
        formula += " + C(semester)"
    elif temporal_granularity == "quarterly" and n_years == 1:
        print("  Warning: Single-year quarterly data detected, skipping seasonal dummies to avoid multicollinearity")
    elif temporal_granularity == "semiannual" and n_years == 1:
        print("  Warning: Single-year semiannual data detected, skipping seasonal dummies to avoid multicollinearity")

    # random effects: intercept + slope per entity
    random_formulas = {
        "re_int": f"0 + C({entity_col})",
        "re_slope": f"0 + C({entity_col}):time",
    }

    # fit poisson bayesian mixed model
    glmm_model = PoissonBayesMixedGLM.from_formula(
        formula,
        random_formulas,
        df_prepared,
        vcp_p=vcp_p,
        fe_p=fe_p,
    )

    # DIAGNOSTIC LOGGING
    print(f"\n[GLMM DEBUG] Formula: {formula}")
    print(f"[GLMM DEBUG] N observations: {len(df_prepared)}")
    print(f"[GLMM DEBUG] N entities: {df_prepared[entity_col].nunique()}")
    print(f"[GLMM DEBUG] Year range: {df_prepared['year'].min()}-{df_prepared['year'].max()}")
    print(f"[GLMM DEBUG] Time variable: mean={df_prepared['time'].mean():.6f}, std={df_prepared['time'].std():.6f}")
    print(f"[GLMM DEBUG] Entity sample: {df_prepared[entity_col].unique()[:5].tolist()}")
    print(f"[GLMM DEBUG] vcp_p={vcp_p}, fe_p={fe_p}")
    
    # Print first entity's data
    first_entity = df_prepared[entity_col].iloc[0]
    entity_data = df_prepared[df_prepared[entity_col] == first_entity]
    print(f"\n[GLMM DEBUG] First entity '{first_entity}' data:")
    debug_cols = [c for c in ["year", "quarter", "semester", entity_col, "count", "time"] if c in entity_data.columns]
    print(entity_data[debug_cols].head(10).to_string())

    # use variational bayes (returns posterior mean)
    # avoids boundary convergence issues vs map
    _apply_random_seed()
    glmm_result = glmm_model.fit_vb()

    # extract random effects
    intercepts_dict, slopes_dict = _extract_random_effects(glmm_model, glmm_result)

    # convert to lists for dataframe
    entities = list(intercepts_dict.keys())
    intercepts = [intercepts_dict[ent] for ent in entities]
    slopes = [slopes_dict[ent] for ent in entities]

    # create results dataframe
    df_random_effects = pd.DataFrame(
        {"entity": entities, "Random_Intercept": intercepts, "Random_Slope": slopes}
    )

    # calculate totals from original filtered data
    df_totals = (
        df.groupby(entity_col).size().reset_index(name="count").sort_values(entity_col)
    )

    # merge
    results_df = df_random_effects.merge(
        df_totals, left_on="entity", right_on=entity_col, how="left"
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
