"""Display and summary utilities."""

import pandas as pd


def display_quadrant_summary(
    results_df: pd.DataFrame,
    entity_name: str = "Entity",
    min_count: int = 10
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

    print("\nQuadrant Breakdown:")
    print("-" * 40)

    quadrant_order = ["Q1", "Q2", "Q3", "Q4"]
    quadrant_labels = {
        "Q1": "Q1 (Crisis - High volume, High growth)",
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
                    entity_val = row.get("entity", row.get("Topic", "Unknown"))
                    print(f"  {entity_val} ({int(row['count'])} count)")


def display_transition_summary(
    transitions_df: pd.DataFrame,
    entity_name: str = "Entity"
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
            print("-" * 40)

            # show up to 5 examples
            for _, transition in group.head(5).iterrows():
                print(f"{transition['entity']}")
                print(
                    f"  {transition['from_quadrant']} -> {transition['to_quadrant']} "
                    f"({transition['transition_quarter']})"
                )
                print(f"  {transition['transition_type']}")
                if 'volume_change' in transition:
                    print(f"  Volume change: {transition['volume_change']:.3f}")
                if 'growth_change' in transition:
                    print(f"  Growth change: {transition['growth_change']:.3f}")
                print()  # blank line between transitions

            if len(group) > 5:
                print(f"... and {len(group) - 5} more")


def display_movement_summary(
    movement_df: pd.DataFrame,
    entity_name: str = "Entity"
) -> None:
    """
    Print movement tracking summary.

    Args:
        movement_df: DataFrame from track_cumulative_movement()
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
        print(f"\nQuadrant divergences from global baseline: {divergences} ({div_pct:.1f}%)")
        print("(Period quadrant != Global quadrant)")

    # show entities with largest movements
    if "x_delta" in movement_df.columns and "y_delta" in movement_df.columns:
        entity_total_movement = movement_df.groupby("entity").agg({
            "x_delta": lambda x: abs(x).sum(),
            "y_delta": lambda x: abs(x).sum(),
        })
        entity_total_movement["total"] = (
            entity_total_movement["x_delta"] + entity_total_movement["y_delta"]
        )
        top_movers = entity_total_movement.nlargest(5, "total")

        print(f"\nTop {entity_name.lower()}s by total movement:")
        print("-" * 40)
        for entity, row in top_movers.iterrows():
            print(f"  {entity}: {row['total']:.2f} (X: {row['x_delta']:.2f}, Y: {row['y_delta']:.2f})")


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

    summary = pd.DataFrame({
        "quadrant": counts.index,
        "count": counts.values,
        "percentage": (counts.values / total * 100).round(1)
    })

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

    summary = pd.DataFrame({
        "risk_level": counts.index,
        "count": counts.values,
        "percentage": (counts.values / total * 100).round(1)
    })

    # sort by risk level
    risk_order = {"critical": 0, "high": 1, "medium": 2, "low": 3, "stable": 4}
    summary["order"] = summary["risk_level"].map(risk_order)
    summary = summary.sort_values("order").drop("order", axis=1)

    return summary
