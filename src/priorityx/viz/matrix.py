"""Priority matrix scatter plot visualization."""

from typing import List, Optional, Tuple

import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import pandas as pd
from matplotlib.lines import Line2D

# try to import adjustText for label positioning
try:
    from adjustText import adjust_text
    ADJUSTTEXT_AVAILABLE = True
except ImportError:
    ADJUSTTEXT_AVAILABLE = False
    print("Warning: adjustText not available. Labels may overlap.")


def plot_priority_matrix(
    results_df: pd.DataFrame,
    entity_name: str = "Entity",
    title: Optional[str] = None,
    figsize: Tuple[int, int] = (16, 12),
    top_n_labels: int = 5,
    show_quadrant_labels: bool = False,
    bubble_col: Optional[str] = None,
    force_show_labels: Optional[List[str]] = None,
    force_hide_labels: Optional[List[str]] = None,
    skip_label_min_count: int = 0,
    save_plot: bool = False,
    save_csv: bool = False,
    output_dir: str = "plot",
    temporal_granularity: str = "quarterly",
) -> plt.Figure:
    """
    Visualize priority matrix as scatter plot.

    Creates a quadrant-based scatter plot showing entity positions based on
    GLMM random effects (volume and growth).

    Args:
        results_df: Results from fit_priority_matrix()
                   Required columns: entity, Random_Intercept, Random_Slope, quadrant, count
        entity_name: Name for entity type (e.g., "Service", "Component")
        title: Optional custom title
        figsize: Figure size (width, height)
        top_n_labels: Number of entities to label per quadrant
        show_quadrant_labels: Show quadrant descriptions as background text
        bubble_col: Optional column for bubble sizing (e.g., "count")
        force_show_labels: List of entity names to always label
        force_hide_labels: List of entity names to never label
        skip_label_min_count: Skip labeling entities with count < threshold
        save_plot: Save plot to file
        save_csv: Save data to CSV
        output_dir: Output directory for saved files
        temporal_granularity: Time granularity ('quarterly', 'yearly', 'semiannual')

    Returns:
        Matplotlib figure

    Examples:
        >>> # basic plot
        >>> fig = plot_priority_matrix(results_df, entity_name="Service")

        >>> # with custom bubble sizing and labels
        >>> fig = plot_priority_matrix(
        ...     results_df,
        ...     entity_name="Component",
        ...     bubble_col="count",
        ...     top_n_labels=10,
        ...     save_plot=True
        ... )
    """
    # make a copy to avoid modifying original
    df = results_df.copy()

    # determine bubble sizing
    if bubble_col and bubble_col in df.columns:
        # use log scaling for bubble sizes
        import numpy as np
        df["size"] = 100 + 900 * (np.log1p(df[bubble_col]) / np.log1p(df[bubble_col].max()))
    else:
        # uniform bubble size
        df["size"] = 200

    # select entities to label
    df_labelable = df.copy()
    if skip_label_min_count > 0 and "count" in df.columns:
        df_labelable = df[df["count"] >= skip_label_min_count]

    # get top N by volume and growth in each quadrant
    topics_to_label = {}
    for q in ["Q1", "Q2", "Q3", "Q4"]:
        topics_to_label[q] = []
        q_data = df_labelable[df_labelable["quadrant"] == q]

        if not q_data.empty:
            # top by volume
            if "count" in q_data.columns:
                top_volume = q_data.nlargest(top_n_labels, "count").index.tolist()
                topics_to_label[q].extend(top_volume)

            # top by growth
            top_growth = q_data.nlargest(top_n_labels, "Random_Slope").index.tolist()
            for idx in top_growth:
                if idx not in topics_to_label[q]:
                    topics_to_label[q].append(idx)

    # apply manual label controls
    if force_show_labels:
        for label_name in force_show_labels:
            matches = df[df["entity"] == label_name]
            for idx in matches.index:
                q = df.loc[idx, "quadrant"]
                if idx not in topics_to_label[q]:
                    topics_to_label[q].append(idx)

    if force_hide_labels:
        for label_name in force_hide_labels:
            matches = df[df["entity"] == label_name]
            for idx in matches.index:
                q = df.loc[idx, "quadrant"]
                if idx in topics_to_label[q]:
                    topics_to_label[q].remove(idx)

    # create plot
    plt.figure(figsize=figsize)

    # define colors for each quadrant
    colors = {
        "Q1": "#c2104b",  # red - crisis
        "Q2": "#FF9636",  # orange - investigate
        "Q3": "#5cb85c",  # green - monitor
        "Q4": "#792f88",  # purple - low priority
    }

    # plot all points
    for q, color in colors.items():
        q_data = df[df["quadrant"] == q]
        if not q_data.empty:
            plt.scatter(
                q_data["Random_Intercept"],
                q_data["Random_Slope"],
                s=q_data["size"],
                color=color,
                alpha=0.7,
                label=f"Q{q[-1]}",
                zorder=2,
            )

    # add axis lines
    plt.axhline(0, color="grey", linestyle="--", alpha=0.7, linewidth=1)
    plt.axvline(0, color="grey", linestyle="--", alpha=0.7, linewidth=1)

    # get current axis
    ax = plt.gca()

    # add quadrant labels as background text
    if show_quadrant_labels:
        xlim = ax.get_xlim()
        ylim = ax.get_ylim()

        # compute quadrant centers
        quadrant_centers = {
            "Q1": ((0 + xlim[1]) / 2, (0 + ylim[1]) / 2),  # top right
            "Q2": ((xlim[0] + 0) / 2, (0 + ylim[1]) / 2),  # top left
            "Q3": ((xlim[0] + 0) / 2, (ylim[0] + 0) / 2),  # bottom left
            "Q4": ((0 + xlim[1]) / 2, (ylim[0] + 0) / 2),  # bottom right
        }

        # quadrant descriptions
        quadrant_labels = {
            "Q1": "Q1: Crisis\n(High volume, High growth)",
            "Q2": "Q2: Investigate\n(Low volume, High growth)",
            "Q3": "Q3: Monitor\n(Low volume, Low growth)",
            "Q4": "Q4: Low Priority\n(High volume, Low growth)",
        }

        # place labels
        for q, (cx, cy) in quadrant_centers.items():
            ax.text(
                cx, cy,
                quadrant_labels[q],
                ha="center",
                va="center",
                fontsize=14,
                color="gray",
                alpha=0.45,
                zorder=0,
                fontweight="bold",
            )

    # add entity labels
    texts = []
    for q in ["Q1", "Q2", "Q3", "Q4"]:
        q_data = df[df["quadrant"] == q]
        for entity_idx in topics_to_label[q]:
            if entity_idx in q_data.index:
                row = q_data.loc[entity_idx]
                label = row["entity"]

                text = plt.text(
                    row["Random_Intercept"],
                    row["Random_Slope"],
                    label,
                    fontsize=14,
                    ha="center",
                    va="center",
                )
                texts.append(text)

    # use adjustText to prevent overlaps if available
    if ADJUSTTEXT_AVAILABLE and texts:
        adjust_text(
            texts,
            arrowprops=dict(
                arrowstyle="->", color="gray", lw=1.0, alpha=0.7, shrinkA=5, shrinkB=5
            ),
            expand_points=(1.5, 1.5),
            expand_text=(1.2, 1.2),
            force_text=(0.5, 0.5),
            force_points=(0.3, 0.3),
        )

    # fix y-axis formatter
    ax.yaxis.set_major_locator(
        ticker.MaxNLocator(integer=False, steps=[1, 2, 5], nbins=7)
    )
    ax.yaxis.set_major_formatter(ticker.FormatStrFormatter("%.1f"))

    # create legend with equal-sized bubbles
    legend_elements = []
    for q, color in colors.items():
        legend_elements.append(
            Line2D(
                [0], [0],
                marker="o",
                color="w",
                markerfacecolor=color,
                markersize=10,
                label=f"Quadrant {q[-1]}",
            )
        )

    # set labels
    plt.xlabel(f"{entity_name} Volume (Relative)", fontsize=13)
    plt.ylabel(f"{entity_name} Growth Rate (Relative)", fontsize=13)

    # add title if provided
    if title:
        plt.title(title, fontsize=16, fontweight="bold", pad=20)

    # place legend
    plt.legend(
        handles=legend_elements, loc="lower right", frameon=False, title="Quadrants"
    )

    plt.tight_layout()

    # add bubble size note if applicable
    if bubble_col:
        xlim = ax.get_xlim()
        ylim = ax.get_ylim()
        ax.text(
            xlim[0] + (xlim[1] - xlim[0]) * 0.02,
            ylim[0] + (ylim[1] - ylim[0]) * 0.02,
            f"Bubble size represents {bubble_col}",
            ha="left",
            va="bottom",
            fontsize=10,
            style="italic",
            alpha=0.7,
            zorder=3,
        )

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
        save_path = f"{output_dir}/priority_matrix-{entity_name.lower()}-{granularity_suffix}-{timestamp}.png"

        plt.savefig(save_path, dpi=300, bbox_inches="tight", format="png")
        print(f"Plot saved: {save_path}")

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
        csv_path = f"{output_dir}/../results/priority_matrix-{entity_name.lower()}-{granularity_suffix}-{timestamp}.csv"

        # save key columns
        cols_to_save = ["entity", "quadrant", "Random_Intercept", "Random_Slope", "count"]
        df[[c for c in cols_to_save if c in df.columns]].to_csv(
            csv_path, index=False
        )
        print(f"CSV saved: {csv_path}")

    return plt.gcf()
