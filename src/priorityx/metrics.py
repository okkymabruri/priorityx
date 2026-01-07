"""Helpers for per-entity metrics and simple indices.

These utilities are intentionally small and generic so that downstream
monitoring or early-warning pipelines can build on top of their own
cleaned event data.

The functions here do **not** perform heavy data cleaning or
winsorisation; they assume the caller has already prepared numeric
inputs and focus on predictable aggregation and index construction.
"""

from __future__ import annotations


import numpy as np
import pandas as pd


def aggregate_entity_metrics(
    df: pd.DataFrame,
    entity_col: str,
    *,
    duration_start_col: str | None = None,
    duration_end_col: str | None = None,
    primary_col: str | None = None,
    secondary_col: str | None = None,
) -> pd.DataFrame:
    """Aggregate a few basic per-entity metrics.

    Parameters
    ----------
    df:
        Input DataFrame with one row per event.
    entity_col:
        Column identifying the entity (for example a product, provider, or topic).
    duration_start_col / duration_end_col:
        Optional timestamp columns used to compute ``mean_duration``.
    Primary / secondary magnitude columns:
        Optional numeric columns that are summed per-entity as generic
        "primary" and "secondary" magnitudes (for example volumes, values,
        severities, or any other numeric scores).

    Returns
    -------
    DataFrame with one row per entity containing, when available:

    - ``entity_col``
    - ``mean_duration`` (if duration columns are provided)
    - ``total_primary`` (if a primary magnitude column is provided)
    - ``total_secondary`` (if a secondary magnitude column is provided)
    - ``secondary_to_primary_ratio`` (secondary / primary when primary > 0)
    """

    df_local = df.copy()

    parts: list[pd.DataFrame] = []

    # Durations
    if duration_start_col and duration_end_col:
        if {
            duration_start_col,
            duration_end_col,
        }.issubset(df_local.columns):
            res = df_local.dropna(subset=[duration_start_col, duration_end_col]).copy()
            res[duration_start_col] = pd.to_datetime(res[duration_start_col])
            res[duration_end_col] = pd.to_datetime(res[duration_end_col])
            res["duration_days"] = (
                res[duration_end_col] - res[duration_start_col]
            ).dt.days
            res = res[res["duration_days"] >= 0]
            agg_res = (
                res.groupby(entity_col)["duration_days"].mean().rename("mean_duration")
            )
            parts.append(agg_res.reset_index())

    # Numeric magnitudes (primary / secondary).
    primary_field = primary_col
    secondary_field = secondary_col

    if primary_field or secondary_field:
        amt = df_local.copy()
        if primary_field and primary_field in amt.columns:
            amt[primary_field] = pd.to_numeric(amt[primary_field], errors="coerce")
        if secondary_field and secondary_field in amt.columns:
            amt[secondary_field] = pd.to_numeric(amt[secondary_field], errors="coerce")

        agg_cols: list[str] = []
        rename_map: dict[str, str] = {}
        if primary_field and primary_field in amt.columns:
            agg_cols.append(primary_field)
            rename_map[primary_field] = "total_primary"
        if secondary_field and secondary_field in amt.columns:
            agg_cols.append(secondary_field)
            rename_map[secondary_field] = "total_secondary"

        if agg_cols:
            sums = (
                amt.groupby(entity_col)[agg_cols]
                .sum()
                .rename(columns=rename_map)
                .reset_index()
            )
            parts.append(sums)

    if not parts:
        return pd.DataFrame({entity_col: df_local[entity_col].unique()})

    out = parts[0]
    for part in parts[1:]:
        out = out.merge(part, on=entity_col, how="outer")

    # secondary_to_primary_ratio from totals
    if {"total_primary", "total_secondary"}.issubset(out.columns):
        out["secondary_to_primary_ratio"] = out.apply(
            lambda r: (r["total_secondary"] / r["total_primary"])
            if (
                pd.notna(r.get("total_secondary"))
                and pd.notna(r.get("total_primary"))
                and r["total_primary"] > 0
            )
            else np.nan,
            axis=1,
        )

    return out


def _zscore(series: pd.Series) -> pd.Series:
    """Return a simple z-score transformation, guarding zero std."""

    if series.empty:
        return series.astype(float)
    mean = series.mean()
    std = series.std(ddof=0)
    if std == 0 or pd.isna(std):
        return pd.Series(np.zeros(len(series)), index=series.index, dtype=float)
    return (series - mean) / std


def add_priority_indices(
    df: pd.DataFrame,
    *,
    # Column mappings (set to None if not available)
    volume_col: str = "count",
    growth_col: str = "y_score",
    severity_col: str | None = None,
    resolution_col: str | None = None,
    recovery_col: str | None = None,
    # RI weights (Risk Index)
    w_volume: float = 0.4,
    w_growth: float = 0.4,
    w_severity: float = 0.2,
    # SQI weights (Service Quality Index)
    w_resolution: float = 0.5,
    w_recovery: float = 0.5,
    # EWI weights (Early Warning Index)
    w_risk: float = 0.7,
    w_quality: float = 0.3,
) -> pd.DataFrame:
    """Add composite index columns for risk prioritization.

    This function computes three indices with configurable weights:

    - **RI (Risk Index)**: Measures entity risk from event patterns
      RI = w_volume * z(volume) + w_growth * z(growth) + w_severity * z(severity)

    - **SQI (Service Quality Index)**: Measures service performance (higher = better)
      SQI = w_resolution * z(-resolution) + w_recovery * z(recovery_ratio)

    - **EWI (Early Warning Index)**: Composite score for prioritization
      EWI = w_risk * RI + w_quality * (-SQI)

    Parameters
    ----------
    df : pd.DataFrame
        Input DataFrame with GLMM results and entity metrics.
    volume_col : str
        Column for event volume (count).
    growth_col : str
        Column for growth score (y_score from GLMM).
    severity_col : str | None
        Column for severity/magnitude metric (e.g., total_amount).
    resolution_col : str | None
        Column for resolution speed (e.g., mean_duration).
    recovery_col : str | None
        Column for recovery/outcome ratio.
    w_volume, w_growth, w_severity : float
        Weights for RI components (should sum to 1.0).
    w_resolution, w_recovery : float
        Weights for SQI components (should sum to 1.0).
    w_risk, w_quality : float
        Weights for EWI components (should sum to 1.0).

    Returns
    -------
    pd.DataFrame
        DataFrame with added index columns: RI, SQI, EWI, and z-scored components.

    Examples
    --------
    >>> enriched = add_priority_indices(
    ...     results,
    ...     growth_col="y_score",
    ...     severity_col="total_amount",
    ...     w_volume=0.4, w_growth=0.4, w_severity=0.2,
    ... )
    >>> top_risks = enriched.nlargest(10, "EWI")
    """
    out = df.copy()

    # Z-score components
    z_components = {}

    if volume_col in out.columns:
        z_components["z_volume"] = _zscore(pd.to_numeric(out[volume_col], errors="coerce"))
    if growth_col in out.columns:
        z_components["z_growth"] = _zscore(pd.to_numeric(out[growth_col], errors="coerce"))
    if severity_col and severity_col in out.columns:
        z_components["z_severity"] = _zscore(
            pd.to_numeric(out[severity_col], errors="coerce").fillna(0)
        )
    if resolution_col and resolution_col in out.columns:
        # Negate so higher = faster = better
        z_components["z_neg_resolution"] = _zscore(
            -pd.to_numeric(out[resolution_col], errors="coerce").fillna(
                out[resolution_col].median() if resolution_col in out.columns else 0
            )
        )
    if recovery_col and recovery_col in out.columns:
        z_components["z_recovery"] = _zscore(
            pd.to_numeric(out[recovery_col], errors="coerce").fillna(0)
        )

    # Add z-score columns to output
    for name, values in z_components.items():
        out[name] = values

    # RI: Risk Index
    ri_parts = []
    ri_weights = []
    if "z_volume" in z_components:
        ri_parts.append(z_components["z_volume"])
        ri_weights.append(w_volume)
    if "z_growth" in z_components:
        ri_parts.append(z_components["z_growth"])
        ri_weights.append(w_growth)
    if "z_severity" in z_components:
        ri_parts.append(z_components["z_severity"])
        ri_weights.append(w_severity)

    if ri_parts:
        # Normalize weights if they don't sum to 1
        total_w = sum(ri_weights)
        if total_w > 0:
            ri_weights = [w / total_w for w in ri_weights]
        out["RI"] = sum(w * p for w, p in zip(ri_weights, ri_parts))

    # SQI: Service Quality Index (higher = better service)
    sqi_parts = []
    sqi_weights = []
    if "z_neg_resolution" in z_components:
        sqi_parts.append(z_components["z_neg_resolution"])
        sqi_weights.append(w_resolution)
    if "z_recovery" in z_components:
        sqi_parts.append(z_components["z_recovery"])
        sqi_weights.append(w_recovery)

    if sqi_parts:
        total_w = sum(sqi_weights)
        if total_w > 0:
            sqi_weights = [w / total_w for w in sqi_weights]
        out["SQI"] = sum(w * p for w, p in zip(sqi_weights, sqi_parts))

    # EWI: Early Warning Index (higher = higher priority)
    ewi_parts = []
    ewi_weights = []
    if "RI" in out.columns:
        ewi_parts.append(out["RI"])
        ewi_weights.append(w_risk)
    if "SQI" in out.columns:
        # Invert SQI: lower quality = higher warning
        ewi_parts.append(-out["SQI"])
        ewi_weights.append(w_quality)

    if ewi_parts:
        total_w = sum(ewi_weights)
        if total_w > 0:
            ewi_weights = [w / total_w for w in ewi_weights]
        out["EWI"] = sum(w * p for w, p in zip(ewi_weights, ewi_parts))

    # Backward compatibility: also compute legacy indices
    if {"z_volume", "z_growth"}.issubset(z_components):
        legacy_parts = [z_components["z_volume"], z_components["z_growth"]]
        if "z_severity" in z_components:
            legacy_parts.append(z_components["z_severity"])
        out["volume_growth_index"] = pd.concat(legacy_parts, axis=1).mean(axis=1)

    if {"z_neg_resolution", "z_recovery"}.issubset(z_components):
        out["service_quality_index"] = pd.concat(
            [z_components["z_neg_resolution"], z_components["z_recovery"]], axis=1
        ).mean(axis=1)

    if {"volume_growth_index", "service_quality_index"}.issubset(out.columns):
        out["early_warning_index"] = out[
            ["volume_growth_index", "service_quality_index"]
        ].mean(axis=1)

    return out


def sensitivity_analysis(
    df: pd.DataFrame,
    index_func: callable = None,
    weight_variations: list[dict] | None = None,
    top_n: int = 10,
    entity_col: str = "entity",
    index_col: str = "EWI",
) -> pd.DataFrame:
    """Perform sensitivity analysis on index weight variations.

    Tests how stable the top-N rankings are across different weight configurations.

    Parameters
    ----------
    df : pd.DataFrame
        Input DataFrame for index computation.
    index_func : callable
        Function that takes df and weight kwargs, returns DataFrame with index.
        If None, uses add_priority_indices.
    weight_variations : list[dict]
        List of weight configurations to test. Each dict contains weight params.
        If None, uses default CRI weight variations.
    top_n : int
        Number of top entities to compare across variations.
    entity_col : str
        Column identifying entities.
    index_col : str
        Index column to rank by.

    Returns
    -------
    pd.DataFrame
        Summary showing rank stability across weight variations.

    Examples
    --------
    >>> stability = sensitivity_analysis(
    ...     enriched,
    ...     weight_variations=[
    ...         {"w_volume": 0.5, "w_growth": 0.3, "w_severity": 0.2},
    ...         {"w_volume": 0.4, "w_growth": 0.4, "w_severity": 0.2},
    ...         {"w_volume": 0.3, "w_growth": 0.5, "w_severity": 0.2},
    ...     ],
    ... )
    """
    if index_func is None:
        index_func = add_priority_indices

    if weight_variations is None:
        # Default: vary CRI weights
        weight_variations = [
            {"w_volume": 0.5, "w_growth": 0.3, "w_severity": 0.2},
            {"w_volume": 0.4, "w_growth": 0.4, "w_severity": 0.2},
            {"w_volume": 0.3, "w_growth": 0.5, "w_severity": 0.2},
            {"w_volume": 0.4, "w_growth": 0.3, "w_severity": 0.3},
        ]

    results = []
    for i, weights in enumerate(weight_variations):
        indexed = index_func(df, **weights)
        if index_col not in indexed.columns:
            continue
        top_entities = indexed.nlargest(top_n, index_col)[entity_col].tolist()
        results.append({
            "variation": i + 1,
            "weights": str(weights),
            "top_entities": top_entities,
        })

    if not results:
        return pd.DataFrame()

    # Compute rank stability
    all_top = [set(r["top_entities"]) for r in results]
    if len(all_top) > 1:
        # Core entities: appear in ALL variations
        core = set.intersection(*all_top)
        # Stable entities: appear in most variations (>= 50%)
        from collections import Counter
        entity_counts = Counter(e for r in results for e in r["top_entities"])
        stable = {e for e, c in entity_counts.items() if c >= len(results) / 2}

        for r in results:
            r["core_overlap"] = len(set(r["top_entities"]) & core)
            r["stable_overlap"] = len(set(r["top_entities"]) & stable)

    return pd.DataFrame(results)
