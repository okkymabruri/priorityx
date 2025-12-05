"""Helpers for per-entity metrics and simple indices.

These utilities are intentionally small and generic so that downstream
monitoring or early-warning pipelines can build on top of their own
cleaned event data.

The functions here do **not** perform heavy data cleaning or
winsorisation; they assume the caller has already prepared numeric
inputs and focus on predictable aggregation and index construction.
"""

from __future__ import annotations

from typing import Iterable

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
            res = df_local.dropna(
                subset=[duration_start_col, duration_end_col]
            ).copy()
            res[duration_start_col] = pd.to_datetime(res[duration_start_col])
            res[duration_end_col] = pd.to_datetime(res[duration_end_col])
            res["duration_days"] = (
                res[duration_end_col] - res[duration_start_col]
            ).dt.days
            res = res[res["duration_days"] >= 0]
            agg_res = (
                res.groupby(entity_col)["duration_days"].mean().rename(
                    "mean_duration"
                )
            )
            parts.append(agg_res.reset_index())

    # Numeric magnitudes (primary / secondary).
    primary_field = primary_col
    secondary_field = secondary_col

    if primary_field or secondary_field:
        amt = df_local.copy()
        if primary_field and primary_field in amt.columns:
            amt[primary_field] = pd.to_numeric(
                amt[primary_field], errors="coerce"
            )
        if secondary_field and secondary_field in amt.columns:
            amt[secondary_field] = pd.to_numeric(
                amt[secondary_field], errors="coerce"
            )

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
            if (pd.notna(r.get("total_secondary"))
                and pd.notna(r.get("total_primary"))
                and r["total_primary"] > 0)
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
    volume_col: str = "count",
    growth_col: str = "Random_Slope",
    magnitude_col: str | None = "total_primary",
    duration_col: str | None = "mean_duration",
    ratio_col: str | None = "secondary_to_primary_ratio",
) -> pd.DataFrame:
    """Add a few simple index columns on top of GLMM-style results.

    The intent is to provide weakly opinionated defaults for combining
    volume, growth, and basic outcome metrics into composite scores.
    Callers remain free to ignore or override these.
    """

    out = df.copy()

    cols: Iterable[str] = [volume_col, growth_col]

    if magnitude_col:
        cols = list(cols) + [magnitude_col]

    for col in cols:
        if col in out.columns:
            out[f"z_{col}"] = _zscore(pd.to_numeric(out[col], errors="coerce"))

    # Base index: volume + growth (+ optional magnitude)
    base_components = [
        c for c in [f"z_{volume_col}", f"z_{growth_col}"] if c in out.columns
    ]
    if magnitude_col and f"z_{magnitude_col}" in out.columns:
        base_components.append(f"z_{magnitude_col}")

    if base_components:
        out["volume_growth_index"] = out[base_components].mean(axis=1)

    # Quality index: shorter duration & higher ratio are better
    if duration_col and ratio_col and {duration_col, ratio_col}.issubset(
        out.columns
    ):
        out["z_neg_duration"] = _zscore(
            -pd.to_numeric(out[duration_col], errors="coerce")
        )
        out["z_ratio"] = _zscore(pd.to_numeric(out[ratio_col], errors="coerce"))
        out["service_quality_index"] = out[[
            "z_neg_duration",
            "z_ratio",
        ]].mean(axis=1)

    # Early warning-style index: blend base and quality indices when available
    components = []
    if "volume_growth_index" in out.columns:
        components.append("volume_growth_index")
    if "service_quality_index" in out.columns:
        components.append("service_quality_index")

    if components:
        out["early_warning_index"] = out[components].mean(axis=1)

    return out
