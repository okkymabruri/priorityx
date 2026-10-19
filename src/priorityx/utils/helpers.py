"""Display and summary utilities."""

import hashlib
import json
import os
import re
import tempfile
from datetime import datetime
from pathlib import Path

import pandas as pd
import numpy as np


def compute_cache_key(df: pd.DataFrame, params: dict, version: str | None = None) -> str:
    """Fingerprint input values/schema and resolved settings for movement reuse.

    Row/index/column order is significant; parameter dictionary order is not.
    Values must be scalar and hashable. This identifies a request, not the
    integrity of a CSV that someone subsequently edits.
    """
    from priorityx import __version__

    def dtype_schema(dtype):
        if isinstance(dtype, pd.CategoricalDtype):
            return [str(dtype), dtype.ordered,
                    [(type(value).__name__, repr(value)) for value in dtype.categories]]
        return str(dtype)

    def scalar(value):
        if isinstance(value, np.generic):
            return value.item()
        raise TypeError(f"Unsupported cache parameter type: {type(value).__name__}")

    index_levels = [df.index.get_level_values(i) for i in range(df.index.nlevels)]
    schema = {
        "cache_version": 1,
        "package_version": __version__ if version is None else version,
        "columns": [(type(col).__name__, repr(col)) for col in df.columns],
        "column_names": [repr(name) for name in df.columns.names],
        "dtypes": [dtype_schema(dtype) for dtype in df.dtypes],
        "index_type": type(df.index).__name__,
        "index_names": [repr(name) for name in df.index.names],
        "index_dtypes": [dtype_schema(level.dtype) for level in index_levels],
        "params": params,
    }
    try:
        digest = hashlib.sha256(json.dumps(
            schema, sort_keys=True, ensure_ascii=False, allow_nan=False, default=scalar,
        ).encode("utf-8"))
        digest.update(pd.util.hash_pandas_object(df, index=True).to_numpy(dtype="<u8").tobytes())
        # Pandas can hash an object integer and its text form identically.
        # Include scalar types for object columns/index levels to distinguish them.
        for values in [*(df.iloc[:, i] for i in range(len(df.columns))), *index_levels]:
            if pd.api.types.is_object_dtype(values.dtype):
                types = pd.Series(values).map(lambda value: f"{type(value).__module__}.{type(value).__qualname__}")
                digest.update(pd.util.hash_pandas_object(types, index=False).to_numpy(dtype="<u8").tobytes())
    except (TypeError, ValueError) as exc:
        raise ValueError("Cannot fingerprint cache inputs; use hashable scalar data and finite settings") from exc
    return digest.hexdigest()[:16]


def _validate_cache_key(key: str) -> None:
    if not isinstance(key, str) or re.fullmatch(r"[0-9a-f]{16}", key) is None:
        raise ValueError("Cache key must contain 16 lowercase hexadecimal characters")


def display_quadrant_summary(
    results_df: pd.DataFrame, entity_name: str = "Entity", min_count: int = 10
) -> None:
    """
    Print quadrant breakdown with counts and percentages.

    Args:
        results_df: Results from fit_priority_matrix()
        entity_name: Name for entity type
        min_count: Minimum count to include in summary (default: 10)

    Examples:
        >>> display_quadrant_summary(results_df, entity_name="Service")
    """
    # filter by minimum count if specified
    if min_count > 0 and "count" in results_df.columns:
        df = results_df[results_df["count"] >= min_count]
    else:
        df = results_df

    print(f"\nQUADRANT ANALYSIS SUMMARY - {entity_name.upper()}S")

    total_entities = len(df)

    print(f"\nTotal {entity_name.lower()}s analyzed: {total_entities}")

    if min_count > 0:
        print(f"(Filtered to ≥{min_count} count)")

    print()
    print("Quadrant Breakdown:")

    quadrant_order = ["Q1", "Q2", "Q3", "Q4"]
    quadrant_labels = {
        "Q1": "Q1 (Critical - High volume, High growth)",
        "Q2": "Q2 (Investigate - Low volume, High growth)",
        "Q3": "Q3 (Monitor - Low volume, Low growth)",
        "Q4": "Q4 (Low Priority - High volume, Low growth)",
    }

    for q in quadrant_order:
        q_data = df[df["quadrant"] == q]
        count = len(q_data)
        pct = (count / total_entities * 100) if total_entities > 0 else 0

        if count > 0:
            print()
            print(f"{quadrant_labels[q]}")
            print(f"Count: {count} ({pct:.1f}%)")

            # show top entities by count if available
            if "count" in q_data.columns:
                top_entities = q_data.nlargest(3, "count")
                print("Top by volume:")
                for _, row in top_entities.iterrows():
                    entity_val = row.get("entity", "Unknown")
                    print(f"  {entity_val} ({int(row['count'])} count)")


def display_transition_summary(
    transitions_df: pd.DataFrame, entity_name: str = "Entity"
) -> None:
    """
    Print transition summary by risk level and type.

    Args:
        transitions_df: DataFrame from extract_transitions()
        entity_name: Name for entity type

    Examples:
        >>> display_transition_summary(transitions_df, entity_name="Service")
    """
    if transitions_df.empty:
        print(f"No transitions detected for {entity_name.lower()}s")
        return

    print(f"\nQUADRANT TRANSITION SUMMARY - {entity_name.upper()}S")

    # group by risk level
    risk_groups = transitions_df.groupby("risk_level")

    for risk_level in ["critical", "high", "medium", "low"]:
        if risk_level in risk_groups.groups:
            group = risk_groups.get_group(risk_level)
            print()
            print(f"{risk_level.upper()} RISK TRANSITIONS ({len(group)} total):")

            # show up to 5 examples
            for _, transition in group.head(5).iterrows():
                print(f"{transition['entity']}")
                print(
                    f"  {transition['from_quadrant']} -> {transition['to_quadrant']} "
                    f"({transition['transition_quarter']})"
                )
                print(f"  {transition['transition_type']}")
                if "volume_change" in transition:
                    print(f"  Volume change: {transition['volume_change']:.3f}")
                if "growth_change" in transition:
                    print(f"  Growth change: {transition['growth_change']:.3f}")
                print()  # blank line between transitions

            if len(group) > 5:
                print(f"... and {len(group) - 5} more")


def display_movement_summary(
    movement_df: pd.DataFrame, entity_name: str = "Entity"
) -> None:
    """
    Print movement tracking summary.

    Args:
        movement_df: DataFrame from track_movement()
        entity_name: Name for entity type

    Examples:
        >>> display_movement_summary(movement_df, entity_name="Service")
    """
    if movement_df.empty:
        print(f"No movement data for {entity_name.lower()}s")
        return

    print(f"\nCUMULATIVE MOVEMENT SUMMARY - {entity_name.upper()}S")

    n_entities = movement_df["entity"].nunique()
    n_periods = movement_df["quarter"].nunique()
    n_observations = len(movement_df)

    print(f"\nEntities tracked: {n_entities}")
    print(f"Time periods: {n_periods}")
    print(f"Total observations: {n_observations}")

    # divergence analysis
    if "quadrant_differs" in movement_df.columns:
        divergences = movement_df["quadrant_differs"].sum()
        div_pct = (divergences / n_observations * 100) if n_observations > 0 else 0
        print(
            f"\nQuadrant divergences from global baseline: {divergences} ({div_pct:.1f}%)"
        )
        print("(Period quadrant != Global quadrant)")

    # show entities with largest movements
    if "x_delta" in movement_df.columns and "y_delta" in movement_df.columns:
        entity_total_movement = movement_df.groupby("entity").agg(
            {
                "x_delta": lambda x: abs(x).sum(),
                "y_delta": lambda x: abs(x).sum(),
            }
        )
        entity_total_movement["total"] = (
            entity_total_movement["x_delta"] + entity_total_movement["y_delta"]
        )
        top_movers = entity_total_movement.nlargest(5, "total")

        print()
        print(f"Top {entity_name.lower()}s by total movement:")
        for entity, row in top_movers.iterrows():
            print(
                f"  {entity}: {row['total']:.2f} (X: {row['x_delta']:.2f}, Y: {row['y_delta']:.2f})"
            )


def get_quadrant_counts(results_df: pd.DataFrame) -> pd.DataFrame:
    """
    Get count of entities in each quadrant.

    Args:
        results_df: Results from fit_priority_matrix()

    Returns:
        DataFrame with quadrant counts and percentages

    Examples:
        >>> counts = get_quadrant_counts(results_df)
        >>> print(counts)
    """
    if results_df.empty:
        return pd.DataFrame(columns=["quadrant", "count", "percentage"])

    counts = results_df["quadrant"].value_counts().sort_index()
    total = len(results_df)

    summary = pd.DataFrame(
        {
            "quadrant": counts.index,
            "count": counts.values,
            "percentage": (counts.values / total * 100).round(1),
        }
    )

    return summary


def get_transition_counts(transitions_df: pd.DataFrame) -> pd.DataFrame:
    """
    Get count of transitions by risk level.

    Args:
        transitions_df: DataFrame from extract_transitions()

    Returns:
        DataFrame with transition counts by risk level

    Examples:
        >>> counts = get_transition_counts(transitions_df)
        >>> print(counts)
    """
    if transitions_df.empty:
        return pd.DataFrame(columns=["risk_level", "count", "percentage"])

    counts = transitions_df["risk_level"].value_counts()
    total = len(transitions_df)

    summary = pd.DataFrame(
        {
            "risk_level": counts.index,
            "count": counts.values,
            "percentage": (counts.values / total * 100).round(1),
        }
    )

    # sort by risk level
    risk_order = {"critical": 0, "high": 1, "medium": 2, "low": 3, "stable": 4}
    summary["order"] = summary["risk_level"].map(risk_order)
    summary = summary.sort_values("order").drop("order", axis=1)

    return summary


def generate_output_path(
    artifact: str,
    entity_name: str,
    temporal_granularity: str = "quarterly",
    output_dir: str = "results/csv",
    extension: str = "csv",
    *,
    key: str | None = None,
) -> str:
    """Generate a standardized output path for saved artifacts.

    Args:
        artifact: Artifact name prefix (e.g., "priority_matrix", "movement")
        entity_name: Friendly entity label (e.g., "Service")
        temporal_granularity: Granularity key for suffix (default: "quarterly")
        output_dir: Directory where file should be saved (default: "results/csv")
        extension: File extension (default: "csv")
        key: Optional request fingerprint instead of a filename date.

    Returns:
        Path within ``output_dir``; relative when the supplied directory is
        relative. Constructing the path also creates the directory.
    """

    granularity_suffix = {
        "quarterly": "Q",
        "yearly": "Y",
        "semiannual": "S",
        "monthly": "M",
    }.get(temporal_granularity, "Q")

    if key is not None:
        _validate_cache_key(key)
    suffix = key if key is not None else datetime.now().strftime("%Y%m%d")
    entity_slug = entity_name.lower().replace(" ", "_")

    os.makedirs(output_dir, exist_ok=True)
    filename = f"{artifact}-{entity_slug}-{granularity_suffix}-{suffix}.{extension}"
    return os.path.join(output_dir, filename)


def save_dataframe_to_csv(
    df: pd.DataFrame,
    artifact: str,
    entity_name: str,
    temporal_granularity: str = "quarterly",
    output_dir: str = "results/csv",
    *,
    key: str | None = None,
) -> str:
    """Save a DataFrame using the standardized naming convention.

    Args:
        df: DataFrame to save
        artifact: Artifact name (e.g., "movement")
        entity_name: Friendly entity label for naming
        temporal_granularity: Granularity key for suffix
        output_dir: Directory where file should live
        key: Optional fingerprint; keyed saves replace atomically on success.

    Returns:
        Path to the saved CSV file.
    """

    output_path = generate_output_path(
        artifact,
        entity_name,
        temporal_granularity=temporal_granularity,
        output_dir=output_dir,
        extension="csv",
        key=key,
    )
    if key is None:
        df.to_csv(output_path, index=False)
    else:
        temporary_path = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w", encoding="utf-8", newline="", delete=False,
                dir=Path(output_path).parent, prefix=f".{Path(output_path).name}.", suffix=".tmp",
            ) as temporary:
                temporary_path = Path(temporary.name)
                df.to_csv(temporary, index=False)
            os.replace(temporary_path, output_path)
        finally:
            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)
    return output_path


def latest_artifact_csv(
    artifact: str,
    entity_name: str,
    output_dir: str = "results/csv",
    temporal_granularity: str | None = None,
    *,
    key: str | None = None,
) -> str | None:
    """Find an exact keyed CSV, or the latest date-only CSV without a key.

    Assumes filenames follow ``generate_output_path`` convention:
    ``<output_dir>/<artifact>-<entity_slug>-<granularity>-<YYYYMMDD>.csv``.

    If ``temporal_granularity`` is provided, restricts matches to that
    granularity suffix (e.g. "Q", "M"); otherwise returns the latest
    CSV across all granularities.
    Keyed lookup never falls back to another key or a date-only file.
    """

    slug = entity_name.lower().replace(" ", "_")
    directory = Path(output_dir)

    if key is not None:
        _validate_cache_key(key)

    if temporal_granularity is not None:
        granularity_suffix = {
            "quarterly": "Q",
            "yearly": "Y",
            "semiannual": "S",
            "monthly": "M",
        }.get(temporal_granularity, "Q")
        if key is not None:
            path = directory / f"{artifact}-{slug}-{granularity_suffix}-{key}.csv"
            return str(path) if path.exists() else None
        pattern = f"{artifact}-{slug}-{granularity_suffix}-*.csv"
    else:
        pattern = f"{artifact}-{slug}-[QYSM]-{key if key is not None else '*'}.csv"

    matches = sorted(path for path in directory.glob(pattern)
                     if path.is_file() and (key is not None or re.fullmatch(r"\d{8}", path.stem.rsplit("-", 1)[-1])))
    return str(matches[-1]) if matches else None
