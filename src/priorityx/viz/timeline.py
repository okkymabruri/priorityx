"""Transition timeline heatmap visualization."""

from typing import List, Literal, Optional, Tuple

import matplotlib.pyplot as plt
import pandas as pd


def plot_transition_timeline(
    transitions_df: pd.DataFrame,
    entity_filter: Optional[List[str]] = None,
    highlight_risk_levels: List[str] = ["critical", "high"],
    filter_risk_levels: List[str] = ["critical", "high", "medium"],
    max_entities: Optional[int] = 20,
    figsize: Tuple[int, int] = (14, 8),
    title: Optional[str] = None,
    x_axis_granularity: Literal["quarterly", "semiannual", "yearly"] = "quarterly",
    sort_by_risk_first: bool = True,
    entity_name: str = "Entity",
    show_all_periods: bool = False,
    save_plot: bool = False,
    save_csv: bool = False,
    output_dir: str = "plot",
    temporal_granularity: str = "quarterly",
) -> plt.Figure:
    """
    Visualize transition timeline as heatmap.

    Creates a timeline showing when entities transition between quadrants,
    color-coded by risk level.

    Args:
        transitions_df: DataFrame from extract_transitions()
                       Required columns: entity, transition_quarter, from_quadrant,
                       to_quadrant, risk_level
        entity_filter: Optional list of entities to include
        highlight_risk_levels: Risk levels to highlight (default: critical, high)
        filter_risk_levels: Only show these risk levels (default: critical, high, medium)
        max_entities: Maximum entities to display (default: 20)
        figsize: Figure size (width, height)
        title: Optional custom title
        x_axis_granularity: Time grouping ('quarterly', 'semiannual', 'yearly')
        sort_by_risk_first: Sort by risk level first (True) or count first (False)
        entity_name: Name for y-axis label
        show_all_periods: Include starting period even if no transitions
        save_plot: Save plot to file
        save_csv: Save data to CSV
        output_dir: Output directory for saved files
        temporal_granularity: Time granularity for file naming

    Returns:
        Matplotlib figure

    Examples:
        >>> # basic timeline
        >>> fig = plot_transition_timeline(transitions_df, entity_name="Service")

        >>> # focus on critical transitions only
        >>> fig = plot_transition_timeline(
        ...     transitions_df,
        ...     filter_risk_levels=["critical"],
        ...     max_entities=10
        ... )
    """
    if transitions_df.empty:
        print("No transitions to visualize")
        return None

    # filter out invalid entities
    df = transitions_df[
        transitions_df["entity"].notna() & (transitions_df["entity"] != "nan")
    ].copy()

    if df.empty:
        print("No valid transitions to visualize")
        return None

    # filter by risk levels
    if filter_risk_levels:
        df = df[df["risk_level"].isin(filter_risk_levels)]
        if df.empty:
            print(f"No transitions with risk levels: {filter_risk_levels}")
            return None

    # apply entity filter
    if entity_filter:
        df = df[df["entity"].isin(entity_filter)]

    # map risk levels to numeric order
    risk_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    df["risk_order"] = df["risk_level"].map(risk_order)

    # aggregate quarters based on granularity
    if x_axis_granularity == "semiannual":
        def quarter_to_semester(q_str):
            if "-Q" in q_str:
                year, quarter = q_str.split("-Q")
                semester = "H1" if int(quarter) <= 2 else "H2"
                return f"{year}-{semester}"
            return q_str
        df["period"] = df["transition_quarter"].apply(quarter_to_semester)
    elif x_axis_granularity == "yearly":
        def quarter_to_year(q_str):
            if "-Q" in q_str:
                return q_str.split("-Q")[0]
            return q_str
        df["period"] = df["transition_quarter"].apply(quarter_to_year)
    else:  # quarterly
        df["period"] = df["transition_quarter"]

    periods = sorted(df["period"].unique())

    # add starting period if requested
    if show_all_periods and len(periods) > 0:
        first_period = periods[0]
        if x_axis_granularity == "semiannual" and "-H" in first_period:
            year, semester = first_period.split("-H")
            prev_semester = "H1" if semester == "H2" else "H2"
            prev_year = str(int(year) - 1) if prev_semester == "H2" else year
            prev_period = f"{prev_year}-{prev_semester}"
            if prev_period not in periods:
                periods = [prev_period] + periods
        elif x_axis_granularity == "quarterly" and "-Q" in first_period:
            year, quarter = first_period.split("-Q")
            prev_q = str((int(quarter) - 2) % 4 + 1)
            prev_year = year if int(quarter) > 1 else str(int(year) - 1)
            prev_period = f"{prev_year}-Q{prev_q}"
            if prev_period not in periods:
                periods = [prev_period] + periods

    # sort entities by priority
    if sort_by_risk_first:
        # sort by: most recent activity, then risk level
        entity_max_period = df.groupby("entity")["period"].max()
        period_rank = {p: i for i, p in enumerate(periods)}
        entity_priority = pd.DataFrame({
            "latest_period": entity_max_period,
            "period_rank": entity_max_period.map(period_rank),
        })

        # get risk level in most recent period
        def get_latest_risk(entity):
            latest_p = entity_priority.loc[entity, "latest_period"]
            entity_trans = df[(df["entity"] == entity) & (df["period"] == latest_p)]
            return entity_trans["risk_order"].min() if len(entity_trans) > 0 else 99

        entity_priority["risk_order"] = entity_priority.index.map(get_latest_risk)
        entity_priority = entity_priority.sort_values(
            ["period_rank", "risk_order"],
            ascending=[False, True]
        )
    else:
        # sort by count/volume
        entity_priority = df.groupby("entity").agg({"risk_order": "min"})
        entity_priority = entity_priority.sort_values("risk_order")

    # limit to top N entities
    if max_entities and len(entity_priority) > max_entities:
        top_entities = entity_priority.head(max_entities).index.tolist()
        df = df[df["entity"].isin(top_entities)]
        entity_priority = entity_priority.loc[top_entities]

    # get entities in priority order
    entities = [e for e in entity_priority.index if e in df["entity"].values]

    # create y-axis positions
    y_positions = {entity: i for i, entity in enumerate(entities)}

    # color map for risk levels
    risk_colors = {
        "critical": "#d62728",  # red
        "high": "#ff7f0e",      # orange
        "medium": "#ffdd57",    # yellow
        "low": "#2ca02c",       # green
    }

    # create figure
    fig, ax = plt.subplots(figsize=figsize)

    # plot transitions
    for _, transition in df.iterrows():
        y_pos = y_positions[transition["entity"]]
        x_pos = periods.index(transition["period"])

        color = risk_colors.get(transition["risk_level"], "#95a5a6")

        # plot circle
        ax.scatter(x_pos, y_pos, s=100, c=color, alpha=0.8, zorder=2)

        # add transition label
        label = f"{transition['from_quadrant']}→{transition['to_quadrant']}"
        ax.annotate(
            label,
            (x_pos, y_pos),
            xytext=(8, 0),
            textcoords="offset points",
            fontsize=9,
            color="black",
            va="center",
            alpha=0.8,
        )

    # customize plot
    ax.set_yticks(range(len(entities)))
    ax.set_yticklabels(entities)
    ax.invert_yaxis()  # highest priority at top

    # x-axis labels
    if x_axis_granularity == "quarterly":
        quarter_to_month = {"Q1": "Mar", "Q2": "Jun", "Q3": "Sep", "Q4": "Dec"}
        period_labels = []
        for p in periods:
            if "-Q" in p:
                year, quarter = p.split("-Q")
                month = quarter_to_month.get(f"Q{quarter}", quarter)
                period_labels.append(f"{month} {year}")
            else:
                period_labels.append(p)
    elif x_axis_granularity == "semiannual":
        period_labels = []
        for p in periods:
            if "-H" in p:
                year, semester = p.split("-H")
                period_labels.append(f"H{semester} {year}")
            else:
                period_labels.append(p)
    else:  # yearly
        period_labels = periods

    ax.set_xticks(range(len(periods)))
    ax.set_xticklabels(period_labels, rotation=45, ha="right")
    ax.set_xlim(-0.5, len(periods) - 0.5)

    # clean up borders
    ax.spines["left"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["top"].set_visible(False)

    # build legend
    legend_elements = []
    for risk_level in ["critical", "high", "medium", "low"]:
        if risk_level in df["risk_level"].values:
            legend_elements.append(
                plt.scatter([], [], s=100, c=risk_colors[risk_level],
                           alpha=0.8, label=risk_level.capitalize())
            )

    if legend_elements:
        ax.legend(
            handles=legend_elements,
            loc="center left",
            bbox_to_anchor=(1.02, 0.5),
            title="Risk Level",
            fontsize=10,
            title_fontsize=11,
            frameon=False,
        )

    # set labels
    xlabel_map = {"quarterly": "Quarter", "semiannual": "Semester", "yearly": "Year"}
    ax.set_xlabel(xlabel_map.get(x_axis_granularity, "Period"), fontsize=13)
    ax.set_ylabel(entity_name, fontsize=13)

    if title:
        ax.set_title(title, fontsize=14, fontweight="bold", pad=20)

    ax.tick_params(axis='both', which='major', labelsize=10)
    plt.tight_layout()

    # save plot if requested
    if save_plot:
        import os
        from datetime import datetime

        os.makedirs(output_dir, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d")
        granularity_suffix = {
            "quarterly": "Q",
            "yearly": "Y",
            "semiannual": "S",
        }.get(temporal_granularity, "Q")
        plot_path = f"{output_dir}/transitions-{entity_name.lower()}-{granularity_suffix}-{timestamp}.png"
        plt.savefig(plot_path, dpi=300, bbox_inches="tight", format="png")
        print(f"Transition plot saved: {plot_path}")

    # save CSV if requested
    if save_csv:
        import os
        from datetime import datetime

        os.makedirs(f"{output_dir}/../results", exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d")
        granularity_suffix = {
            "quarterly": "Q",
            "yearly": "Y",
            "semiannual": "S",
        }.get(temporal_granularity, "Q")
        csv_path = f"{output_dir}/../results/transitions-{entity_name.lower()}-{granularity_suffix}-{timestamp}.csv"
        df.to_csv(csv_path, index=False)
        print(f"Transitions CSV saved: {csv_path}")

    return fig
