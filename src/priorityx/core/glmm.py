"""GLMM estimation for entity prioritization using Poisson and Gaussian mixed models."""

from typing import Dict, Literal, Optional, Tuple
from datetime import timedelta
import os
import warnings
import numpy as np

import pandas as pd
import statsmodels.api as sm
from statsmodels.genmod.bayes_mixed_glm import PoissonBayesMixedGLM, _BayesMixedGLM

# default prior scales for random effects
DEFAULT_VCP_P = 3.5  # random effects prior scale
DEFAULT_FE_P = 3.0  # fixed effects prior scale

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
    """Apply configured random seed before each GLMM fit for determinism."""

    if _GLMM_RANDOM_SEED is not None:
        np.random.seed(_GLMM_RANDOM_SEED)


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


def _zscore_series(values: list[float]) -> list[float]:
    """Z-score normalize a list of values."""
    arr = np.asarray(values, dtype=float)
    if len(arr) == 0:
        return []
    mean = float(arr.mean())
    std = float(arr.std(ddof=0)) or 1.0
    return [(v - mean) / std for v in values]


def _fit_single_glmm(
    df: pd.DataFrame,
    entity_col: str,
    timestamp_col: str,
    *,
    metric_col: Optional[str] = None,
    count_col: Optional[str] = None,
    x_effect: Literal["intercept", "slope"] = "intercept",
    y_effect: Literal["intercept", "slope"] = "slope",
    date_filter: Optional[str] = None,
    min_observations: int = 3,
    min_total_count: int = 0,
    decline_window_quarters: int = 6,
    temporal_granularity: Literal[
        "yearly", "quarterly", "semiannual", "monthly"
    ] = "yearly",
    vcp_p: float = DEFAULT_VCP_P,
    fe_p: float = DEFAULT_FE_P,
    verbose: bool = False,
) -> Tuple[pd.DataFrame, Dict]:
    """Fit a single GLMM and extract x_score/y_score from intercept/slope.

    This is the default mode: fits one GLMM on counts or a single metric,
    then uses Random_Intercept for x_score and Random_Slope for y_score.
    """
    # create copy to avoid modifying original
    df = df.copy()

    if not verbose:
        warnings.filterwarnings(
            "ignore", message="VB fitting did not converge", category=UserWarning
        )

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
        if verbose and n_filtered_volume > 0:
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

        if metric_col:
            df_prepared = (
                df.groupby(["year", "quarter", entity_col])[metric_col]
                .mean()
                .reset_index(name="metric")
                .sort_values(["year", "quarter", entity_col])
            )
        elif count_col:
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

        if metric_col:
            df_prepared = (
                df.groupby(["year", "semester", entity_col])[metric_col]
                .mean()
                .reset_index(name="metric")
                .sort_values(["year", "semester", entity_col])
            )
        elif count_col:
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

    elif temporal_granularity == "monthly":
        df["year"] = df[timestamp_col].dt.year
        df["month"] = df[timestamp_col].dt.month

        if metric_col:
            df_prepared = (
                df.groupby(["year", "month", entity_col])[metric_col]
                .mean()
                .reset_index(name="metric")
                .sort_values(["year", "month", entity_col])
            )
        elif count_col:
            df_prepared = (
                df.groupby(["year", "month", entity_col])[count_col]
                .sum()
                .reset_index(name="count")
                .sort_values(["year", "month", entity_col])
            )
        else:
            df_prepared = (
                df.groupby(["year", "month", entity_col])
                .size()
                .reset_index(name="count")
                .sort_values(["year", "month", entity_col])
            )

    else:  # yearly
        df["year"] = df[timestamp_col].dt.year

        if metric_col:
            df_prepared = (
                df.groupby(["year", entity_col])[metric_col]
                .mean()
                .reset_index(name="metric")
                .sort_values(["year", entity_col])
            )
        elif count_col:
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

    # ensure count is integer (only for count-based models)
    if "count" in df_prepared.columns:
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

    elif temporal_granularity == "monthly":
        # continuous monthly time: year + (month-1)/12
        df_prepared["time_continuous"] = (
            df_prepared["year"] + (df_prepared["month"] - 1) / 12
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
    elif temporal_granularity == "monthly":
        df_prepared["month"] = df_prepared["month"].astype("category")

    # ensure positive counts for poisson (only for count-based models)
    if "count" in df_prepared.columns:
        df_prepared = df_prepared[df_prepared["count"] > 0]
    else:
        # for metric-based models, drop NaN values
        df_prepared = df_prepared[df_prepared["metric"].notna()]

    # track basic metric stats for diagnostics (do not standardize inputs here)
    metric_mean: Optional[float] = None
    metric_std: Optional[float] = None
    if "metric" in df_prepared.columns:
        metric_mean = float(df_prepared["metric"].mean())
        metric_std = float(df_prepared["metric"].std(ddof=0))

    # prepare for statsmodels
    df_prepared["time"] = df_prepared["time"].astype(float)

    # build fixed-effect formula with seasonal dummies
    response_var = "count" if "count" in df_prepared.columns else "metric"
    formula = f"{response_var} ~ time"

    # only add seasonal effects if multi-year data (avoid multicollinearity in single-year)
    n_years = df_prepared["year"].nunique()
    if temporal_granularity == "quarterly" and n_years >= 2:
        formula += " + C(quarter)"
    elif temporal_granularity == "semiannual" and n_years >= 2:
        formula += " + C(semester)"
    elif temporal_granularity == "monthly" and n_years >= 2:
        formula += " + C(month)"
    elif temporal_granularity == "quarterly" and n_years == 1:
        print(
            "  Warning: Single-year quarterly data detected, skipping seasonal dummies to avoid multicollinearity"
        )
    elif temporal_granularity == "semiannual" and n_years == 1:
        print(
            "  Warning: Single-year semiannual data detected, skipping seasonal dummies to avoid multicollinearity"
        )
    elif temporal_granularity == "monthly" and n_years == 1:
        print(
            "  Warning: Single-year monthly data detected, skipping seasonal dummies to avoid multicollinearity"
        )

    # random effects: intercept + slope per entity
    random_formulas = {
        "re_int": f"0 + C({entity_col})",
        "re_slope": f"0 + C({entity_col}):time",
    }

    if metric_col:
        # Gaussian Bayesian mixed model for continuous metrics. We reuse
        # the same random-effects structure as for Poisson counts but
        # with a Gaussian family. Depending on statsmodels version, we
        # fall back from variational Bayes to MAP or MLE.
        glmm_model = _BayesMixedGLM.from_formula(
            formula,
            random_formulas,
            df_prepared,
            family=sm.families.Gaussian(),
            vcp_p=vcp_p,
            fe_p=fe_p,
        )

        if verbose:
            print(
                f"\n[GLMM DEBUG] Formula: {formula}; N={len(df_prepared)}, "
                f"entities={df_prepared[entity_col].nunique()}, "
                f"year_range={df_prepared['year'].min()}-{df_prepared['year'].max()}, "
                f"time_mean={df_prepared['time'].mean():.6f}, time_std={df_prepared['time'].std():.6f}, "
                f"vcp_p={vcp_p}, fe_p={fe_p}"
            )
            print(
                f"[GLMM DEBUG] Entity sample: {df_prepared[entity_col].unique()[:5].tolist()}"
            )

        _apply_random_seed()
        try:
            glmm_result = glmm_model.fit_vb()
            model_method = "GaussianVB"
        except AttributeError:
            # Older statsmodels may not expose fit_vb on _BayesMixedGLM
            try:
                glmm_result = glmm_model.fit_map()
                model_method = "GaussianMAP"
            except AttributeError:
                glmm_result = glmm_model.fit()
                model_method = "GaussianMLE"

        intercepts_dict, slopes_dict = _extract_random_effects(glmm_model, glmm_result)
    else:
        # Poisson Bayesian mixed model for counts
        glmm_model = PoissonBayesMixedGLM.from_formula(
            formula,
            random_formulas,
            df_prepared,
            vcp_p=vcp_p,
            fe_p=fe_p,
        )

        if verbose:
            print(
                f"\n[GLMM DEBUG] Formula: {formula}; N={len(df_prepared)}, "
                f"entities={df_prepared[entity_col].nunique()}, "
                f"year_range={df_prepared['year'].min()}-{df_prepared['year'].max()}, "
                f"time_mean={df_prepared['time'].mean():.6f}, time_std={df_prepared['time'].std():.6f}, "
                f"vcp_p={vcp_p}, fe_p={fe_p}"
            )
            print(
                f"[GLMM DEBUG] Entity sample: {df_prepared[entity_col].unique()[:5].tolist()}"
            )
        # use variational bayes (returns posterior mean)
        # avoids boundary convergence issues vs map
        _apply_random_seed()
        glmm_result = glmm_model.fit_vb()
        intercepts_dict, slopes_dict = _extract_random_effects(glmm_model, glmm_result)
        model_method = "VB"

    # convert to lists for dataframe and, for metric-based models,
    # standardize random effects across entities for a stable index scale
    entities = list(intercepts_dict.keys())
    intercepts = [intercepts_dict[ent] for ent in entities]
    slopes = [slopes_dict[ent] for ent in entities]

    if metric_col and entities:
        # Z-score normalize for metric-based models
        intercepts = _zscore_series(intercepts)
        slopes = _zscore_series(slopes)

    # Map effect type to scores
    # x_effect/y_effect determine which random effect becomes which score
    x_values = intercepts if x_effect == "intercept" else slopes
    y_values = slopes if y_effect == "slope" else intercepts

    # create results dataframe with standardized column names
    df_random_effects = pd.DataFrame(
        {"entity": entities, "x_score": x_values, "y_score": y_values}
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
            row["x_score"],
            row["y_score"],
            count=row.get("count"),
            min_q1_count=30,  # crisis threshold
        ),
        axis=1,
    )

    # model statistics
    model_stats = {
        "n_entities": len(results_df),
        "n_observations": len(df_prepared),
        "method": model_method,
        "vcp_p": vcp_p,
        "fe_p": fe_p,
        "temporal_granularity": temporal_granularity,
        "x_effect": x_effect,
        "y_effect": y_effect,
    }

    if metric_col:
        model_stats["metric_col"] = metric_col
        model_stats["metric_mean"] = metric_mean
        model_stats["metric_std"] = metric_std

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


def _fit_dual_glmm(
    df: pd.DataFrame,
    entity_col: str,
    timestamp_col: str,
    *,
    x_metric: str,
    y_metric: str,
    x_effect: Literal["intercept", "slope"] = "intercept",
    y_effect: Literal["intercept", "slope"] = "intercept",
    date_filter: Optional[str] = None,
    min_observations: int = 3,
    min_total_count: int = 0,
    decline_window_quarters: int = 6,
    temporal_granularity: Literal[
        "yearly", "quarterly", "semiannual", "monthly"
    ] = "yearly",
    vcp_p: float = DEFAULT_VCP_P,
    fe_p: float = DEFAULT_FE_P,
    verbose: bool = False,
) -> Tuple[pd.DataFrame, Dict]:
    """Fit two independent GLMMs for X and Y axes.

    Used when x_metric != y_metric (or one is count-based and one is metric-based).
    """
    # Fit X axis GLMM
    x_is_count = x_metric is None
    x_results, x_stats = _fit_single_glmm(
        df,
        entity_col=entity_col,
        timestamp_col=timestamp_col,
        metric_col=None if x_is_count else x_metric,
        count_col=None,
        x_effect=x_effect,
        y_effect=x_effect,  # same effect for both since we only use x_score
        date_filter=date_filter,
        min_observations=min_observations,
        min_total_count=min_total_count,
        decline_window_quarters=decline_window_quarters,
        temporal_granularity=temporal_granularity,
        vcp_p=vcp_p,
        fe_p=fe_p,
        verbose=verbose,
    )

    # Fit Y axis GLMM
    y_is_count = y_metric is None
    y_results, y_stats = _fit_single_glmm(
        df,
        entity_col=entity_col,
        timestamp_col=timestamp_col,
        metric_col=None if y_is_count else y_metric,
        count_col=None,
        x_effect=y_effect,  # use y_effect for both since we only use x_score
        y_effect=y_effect,
        date_filter=date_filter,
        min_observations=min_observations,
        min_total_count=min_total_count,
        decline_window_quarters=decline_window_quarters,
        temporal_granularity=temporal_granularity,
        vcp_p=vcp_p,
        fe_p=fe_p,
        verbose=verbose,
    )

    # Merge results: take x_score from X GLMM, y_score from Y GLMM (via x_score column)
    x_view = x_results[["entity", "x_score", "count"]].copy()
    y_view = (
        y_results[["entity", "x_score"]].rename(columns={"x_score": "y_score"}).copy()
    )

    out = x_view.merge(y_view, on="entity", how="inner")

    # Recompute quadrant classification based on combined axes
    from .quadrants import classify_quadrant

    out["quadrant"] = out.apply(
        lambda r: classify_quadrant(r["x_score"], r["y_score"], count=r.get("count")),
        axis=1,
    )

    stats = {
        "n_entities": len(out),
        "x_metric": x_metric,
        "y_metric": y_metric,
        "x_effect": x_effect,
        "y_effect": y_effect,
        "x_stats": x_stats,
        "y_stats": y_stats,
        "temporal_granularity": temporal_granularity,
    }

    return out, stats


def fit_priority_matrix(
    df: pd.DataFrame,
    entity_col: str,
    timestamp_col: str,
    *,
    # Axis configuration (optional - defaults to volume x growth)
    x_metric: Optional[str] = None,
    y_metric: Optional[str] = None,
    x_effect: Literal["intercept", "slope"] = "intercept",
    y_effect: Literal["intercept", "slope"] = "slope",
    # Existing params unchanged
    count_col: Optional[str] = None,
    date_filter: Optional[str] = None,
    min_observations: int = 3,
    min_total_count: int = 0,
    decline_window_quarters: int = 6,
    temporal_granularity: Literal[
        "yearly", "quarterly", "semiannual", "monthly"
    ] = "yearly",
    vcp_p: float = DEFAULT_VCP_P,
    fe_p: float = DEFAULT_FE_P,
    verbose: bool = False,
) -> Tuple[pd.DataFrame, Dict]:
    """
    Fit GLMM to classify entities into priority quadrants.

    This is the unified entry point for priority matrix fitting. It supports:

    - **Default mode (volume x growth)**: One GLMM on counts, x_score = intercept, y_score = slope
    - **Custom Y axis**: One GLMM on counts, separate GLMM for y_metric
    - **Custom both axes**: Two independent GLMMs for x_metric and y_metric

    Args:
        df: Input DataFrame with one row per event.
        entity_col: Column identifying the entity (e.g., "service", "product").
        timestamp_col: Date/timestamp column for temporal aggregation.

        x_metric: Optional metric column for X axis. If None, uses count-based GLMM.
        y_metric: Optional metric column for Y axis. If None, uses count-based GLMM.
        x_effect: Which random effect to use for X score ("intercept" or "slope").
        y_effect: Which random effect to use for Y score ("intercept" or "slope").

        count_col: Optional count column (default: row count per entity-period).
        date_filter: Date filter (e.g., "< 2025-01-01", ">= 2024-01-01").
        min_observations: Minimum time periods required per entity.
        min_total_count: Minimum total count threshold to include entity.
        decline_window_quarters: Filter entities inactive >N quarters.
        temporal_granularity: Time aggregation level ("yearly", "quarterly", "semiannual", "monthly").
        vcp_p: Random effects prior scale.
        fe_p: Fixed effects prior scale.
        verbose: Print diagnostic logs.

    Returns:
        Tuple of (results DataFrame, statistics dict).

        Results DataFrame columns:
        - entity: Entity identifier
        - x_score: Normalized score for X axis
        - y_score: Normalized score for Y axis
        - count: Total event count per entity
        - quadrant: Classification (Q1-Q4)

    Examples:
        >>> # Default: volume x growth
        >>> results, stats = px.fit_priority_matrix(
        ...     df,
        ...     entity_col="service",
        ...     timestamp_col="date",
        ... )

        >>> # Custom Y: volume x resolution_days
        >>> results, stats = px.fit_priority_matrix(
        ...     df,
        ...     entity_col="service",
        ...     timestamp_col="date",
        ...     y_metric="resolution_days",
        ... )

        >>> # Custom both: disputed_amount x paid_amount
        >>> results, stats = px.fit_priority_matrix(
        ...     df,
        ...     entity_col="service",
        ...     timestamp_col="date",
        ...     x_metric="disputed_amount",
        ...     y_metric="paid_amount",
        ... )
    """
    # Smart GLMM selection based on axis configuration
    # If both metrics are None (default) or both are the same, use single GLMM
    if x_metric == y_metric:
        # Single GLMM mode: x_score = intercept, y_score = slope (or custom effects)
        return _fit_single_glmm(
            df,
            entity_col=entity_col,
            timestamp_col=timestamp_col,
            metric_col=x_metric,  # same as y_metric
            count_col=count_col,
            x_effect=x_effect,
            y_effect=y_effect,
            date_filter=date_filter,
            min_observations=min_observations,
            min_total_count=min_total_count,
            decline_window_quarters=decline_window_quarters,
            temporal_granularity=temporal_granularity,
            vcp_p=vcp_p,
            fe_p=fe_p,
            verbose=verbose,
        )
    else:
        # Dual GLMM mode: separate models for X and Y axes
        return _fit_dual_glmm(
            df,
            entity_col=entity_col,
            timestamp_col=timestamp_col,
            x_metric=x_metric,
            y_metric=y_metric,
            x_effect=x_effect,
            y_effect=y_effect,
            date_filter=date_filter,
            min_observations=min_observations,
            min_total_count=min_total_count,
            decline_window_quarters=decline_window_quarters,
            temporal_granularity=temporal_granularity,
            vcp_p=vcp_p,
            fe_p=fe_p,
            verbose=verbose,
        )
