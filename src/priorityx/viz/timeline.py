"""Transition timeline heatmap visualization."""

from typing import List, Literal, Optional, Tuple
import warnings

import matplotlib.pyplot as plt
import pandas as pd

from priorityx.tracking.transitions import classify_priority

# suppress noisy FancyArrowPatch fallback warnings from annotate/adjustments
warnings.filterwarnings(
    "ignore",
    message=".*FancyArrowPatch.*",
    category=UserWarning,
)


def plot_transition_timeline(
    transitions_df: pd.DataFrame,
    entity_filter: Optional[List[str]] = None,
    highlight_risk_levels: List[str] = ["critical", "high"],
    filter_risk_levels: Optional[List[str]] = None,
    max_entities: Optional[int] = 20,
    figsize: Tuple[int, int] = (16, 12),
    title: Optional[str] = None,
    x_axis_granularity: Literal[
        "quarterly", "semiannual", "yearly", "monthly"
    ] = "quarterly",
    sort_by_risk_first: bool = True,
    entity_name: str = "Entity",
    show_all_periods: bool = False,
    save_plot: bool = False,
    save_csv: bool = False,
    plot_dir: str = "results/plot",
    csv_dir: str = "results/csv",
    temporal_granularity: str = "quarterly",
    movement_df: Optional[pd.DataFrame] = None,
    close_fig: bool = False,
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
        plot_dir: Output directory for plot files
        csv_dir: Output directory for CSV files
        temporal_granularity: Time granularity for file naming
        movement_df: Optional movement DataFrame for priority calculation
        close_fig: Close the figure before returning (set True if you see duplicate inline renders)

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

    # aggregate periods based on granularity
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
    elif x_axis_granularity == "monthly":
        # use transition_quarter as-is (assumed monthly label like YYYY-MM)
        df["period"] = df["transition_quarter"]
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
        entity_priority = pd.DataFrame(
            {
                "latest_period": entity_max_period,
                "period_rank": entity_max_period.map(period_rank),
            }
        )

        # get risk level in most recent period
        def get_latest_risk(entity):
            latest_p = entity_priority.loc[entity, "latest_period"]
            entity_trans = df[(df["entity"] == entity) & (df["period"] == latest_p)]
            return entity_trans["risk_order"].min() if len(entity_trans) > 0 else 99

        entity_priority["risk_order"] = entity_priority.index.map(get_latest_risk)
        entity_priority = entity_priority.sort_values(
            ["period_rank", "risk_order"], ascending=[False, True]
        )
    else:
        # sort by volume (descending) when movement_df is available.
        # Fallback to risk order if movement data is missing.
        if movement_df is not None and not movement_df.empty:
            vol_col = None
            if "count_total" in movement_df.columns:
                vol_col = "count_total"
            elif "cumulative_count" in movement_df.columns:
                vol_col = "cumulative_count"

            if vol_col is not None:
                volumes = movement_df.groupby("entity")[vol_col].max()
                entity_priority = pd.DataFrame({"volume": volumes})
                # Keep only entities present in the (already filtered) transition set.
                entity_priority = entity_priority.loc[
                    entity_priority.index.intersection(df["entity"].unique())
                ]
                entity_priority = entity_priority.sort_values("volume", ascending=False)
            else:
                entity_priority = df.groupby("entity").agg({"risk_order": "min"})
                entity_priority = entity_priority.sort_values("risk_order")
        else:
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

    # color map for priority levels (4-tier system)
    priority_colors = {
        1: "#d62728",  # red - crisis
        2: "#ff7f0e",  # orange - investigate
        3: "#ffdd57",  # yellow - monitor
        4: "#2ca02c",  # green - low
    }

    # create figure
    fig, ax = plt.subplots(figsize=figsize)

    # plot transitions
    priorities_present = set()
    for _, transition in df.iterrows():
        y_pos = y_positions[transition["entity"]]
        x_pos = periods.index(transition["period"])

        # calculate priority if movement data available
        spike_axis = None
        if movement_df is not None:
            entity_movement = movement_df[
                (movement_df["entity"] == transition["entity"])
                & (movement_df["quarter"] == transition["transition_quarter"])
            ]

            if len(entity_movement) > 0:
                row = entity_movement.iloc[0]
                prev_quarter_data = movement_df[
                    (movement_df["entity"] == transition["entity"])
                    & (movement_df["quarter"] < transition["transition_quarter"])
                ]

                if len(prev_quarter_data) > 0:
                    prev_row = prev_quarter_data.iloc[-1]

                    # use cumulative_count for movement magnitude when available
                    if (
                        "cumulative_count" in row.index
                        and "cumulative_count" in prev_row.index
                    ):
                        count_col = "cumulative_count"

                        complaints_delta = int(row[count_col] - prev_row[count_col])
                        percent_change = (
                            (row[count_col] - prev_row[count_col])
                            / prev_row[count_col]
                            * 100
                            if prev_row[count_col] > 0
                            else 0
                        )

                        priority, _, spike_axis = classify_priority(
                            from_quadrant=transition["from_quadrant"],
                            to_quadrant=transition["to_quadrant"],
                            x=row["period_x"],
                            y=row["period_y"],
                            x_delta=row["period_x"] - prev_row["period_x"],
                            y_delta=row["period_y"] - prev_row["period_y"],
                            complaints_delta=complaints_delta,
                            percent_change=percent_change,
                        )
                    else:
                        priority = 2
                        spike_axis = None
                else:
                    priority = 2  # default to "investigate"
            else:
                priority = 2
        else:
            priority = 2

        priorities_present.add(priority)

        # get priority color
        color = priority_colors.get(priority, "#95a5a6")

        # plot circle
        ax.scatter(x_pos, y_pos, s=100, c=color, alpha=0.8, zorder=2)

        # add transition label with spike indicator
        to_quad = str(transition["to_quadrant"])
        label = f"{transition['from_quadrant']}→{to_quad}"

        # avoid duplicating spike markers when to_quadrant already
        # contains *X / *Y / *XY
        has_inline_spike = "*" in to_quad

        if spike_axis and not has_inline_spike:
            # add superscript indicator
            if spike_axis == "Y":
                label += "*$^Y$"
            elif spike_axis == "X":
                label += "*$^X$"
            elif spike_axis == "XY":
                label += "*$^{XY}$"

        ax.annotate(
            label,
            (x_pos, y_pos),
            xytext=(8, 0),
            textcoords="offset points",
            fontsize=12,
            color="black",
            va="center",
            alpha=0.8,
        )

    # customize plot
    ax.set_yticks(range(len(entities)))
    ax.set_yticklabels(entities, fontsize=15)
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
    elif x_axis_granularity == "yearly":
        period_labels = periods
    else:  # monthly
        period_labels = periods

    ax.set_xticks(range(len(periods)))
    tick_fontsize = 15
    ax.set_xticklabels(period_labels, rotation=45, ha="right", fontsize=tick_fontsize)
    ax.set_xlim(-0.5, len(periods) - 0.5)

    # clean up borders
    ax.spines["left"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["top"].set_visible(False)

    # build legend
    priority_defs = [
        (1, "#d62728", "Crisis"),
        (2, "#ff7f0e", "Investigate"),
        (3, "#ffdd57", "Monitor"),
        (4, "#2ca02c", "Low"),
    ]

    legend_elements = []
    for priority, color, label in priority_defs:
        if priority in priorities_present:
            legend_elements.append(
                plt.scatter([], [], s=100, c=color, alpha=0.8, label=label)
            )

    if legend_elements:
        legend_fontsize = 15
        ax.legend(
            handles=legend_elements,
            loc="center left",
            bbox_to_anchor=(1.02, 0.5),
            title="Priority",
            fontsize=legend_fontsize,
            title_fontsize=legend_fontsize,
            frameon=False,
        )

        # add superscript note below legend
        ax.text(
            1.02,
            0.25,
            "*$^Y$ = Y-axis spike\n*$^X$ = X-axis spike",
            transform=ax.transAxes,
            fontsize=12,
            ha="left",
            va="top",
        )

    # set labels
    xlabel_map = {
        "quarterly": "Quarter",
        "semiannual": "Semester",
        "yearly": "Year",
        "monthly": "Month",
    }
    axis_fontsize = 15
    ax.set_xlabel(xlabel_map.get(x_axis_granularity, "Period"), fontsize=axis_fontsize)
    
    # Use readable y-axis label
    if "fsp" in entity_name.lower():
        ylabel = "FSP"
    elif "topic" in entity_name.lower():
        ylabel = "Topic"
    elif "product" in entity_name.lower():
        ylabel = "Product"
    else:
        ylabel = entity_name
    ax.set_ylabel(ylabel, fontsize=axis_fontsize)
    ax.set_yticklabels(entities, fontsize=tick_fontsize)

    # Only set title if not empty
    if title is None:
        title = f"{entity_name} Transition Timeline"
    if title:  # Skip if empty string
        ax.set_title(title, fontsize=17, fontweight="bold", pad=20)

    ax.tick_params(axis="both", which="major", labelsize=tick_fontsize)
    plt.tight_layout()

    # save plot if requested
    if save_plot:
        import os
        from datetime import datetime

        os.makedirs(plot_dir, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d")
        granularity_suffix = {
            "quarterly": "Q",
            "yearly": "Y",
            "semiannual": "S",
            "monthly": "M",
        }.get(temporal_granularity, "Q")
        plot_path = f"{plot_dir}/transition_timeline-{entity_name.lower()}-{granularity_suffix}-{timestamp}.png"
        plt.savefig(plot_path, dpi=300, bbox_inches="tight", format="png")
        print(f"Transition plot saved: {plot_path}")

    # save CSV if requested
    if save_csv:
        import os
        from datetime import datetime

        os.makedirs(csv_dir, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d")
        granularity_suffix = {
            "quarterly": "Q",
            "yearly": "Y",
            "semiannual": "S",
            "monthly": "M",
        }.get(temporal_granularity, "Q")
        csv_path = f"{csv_dir}/transitions-{entity_name.lower()}-{granularity_suffix}-{timestamp}.csv"

        df_to_save = df
        # For monthly outputs, expose a clearer ``transition_month`` label
        # in the CSV while keeping the internal transition_quarter column
        # for code that relies on it.
        if temporal_granularity == "monthly" and "transition_quarter" in df.columns:
            df_to_save = df.copy().rename(
                columns={"transition_quarter": "transition_month"}
            )

        df_to_save.to_csv(csv_path, index=False)
        print(f"Transitions CSV saved: {csv_path}")

    if close_fig:
        plt.close(fig)

    return fig
