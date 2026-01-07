"""Priority matrix scatter plot visualization."""

from typing import List, Optional, Tuple
import warnings

import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import pandas as pd
from matplotlib.lines import Line2D

from priorityx.core.quadrants import get_quadrant_label

# try to import adjustText for label positioning
try:
    from adjustText import adjust_text

    ADJUSTTEXT_AVAILABLE = True
except ImportError:
    ADJUSTTEXT_AVAILABLE = False
    print("Warning: adjustText not available. Labels may overlap.")

# suppress noisy FancyArrowPatch fallback warnings from adjustText/annotate
warnings.filterwarnings(
    "ignore",
    message=".*FancyArrowPatch.*",
    category=UserWarning,
)


def plot_priority_matrix(
    results_df: pd.DataFrame,
    entity_name: str = "Entity",
    title: Optional[str] = None,
    figsize: Tuple[int, int] = (16, 12),
    top_n_labels: int = 5,
    show_quadrant_labels: bool = True,
    show_legend: bool = True,
    quadrant_label_fontsize: int = 15,
    quadrant_code_fontsize_delta: int = 6,
    bubble_col: Optional[str] = None,
    x_col: str = "x_score",
    y_col: str = "y_score",
    force_show_labels: Optional[List[str]] = None,
    force_hide_labels: Optional[List[str]] = None,
    skip_label_min_count: int = 0,
    save_plot: bool = False,
    save_csv: bool = False,
    plot_dir: str = "results/plot",
    csv_dir: str = "results/csv",
    temporal_granularity: str = "quarterly",
    close_fig: bool = False,
    x_label: Optional[str] = None,
    y_label: Optional[str] = None,
    bubble_scale: float = 0.3,
    legend_loc: str = "lower right",
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
        plot_dir: Output directory for plot files
        csv_dir: Output directory for CSV files
        temporal_granularity: Time granularity ('quarterly', 'yearly', 'semiannual', 'monthly')
        close_fig: Close the figure before returning (set True if you see duplicate inline renders)

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

        # Track null/zero bubble values for hollow ring rendering
        df["_has_bubble"] = df[bubble_col].notna() & (df[bubble_col] > 0)
        
        # For valid bubbles, calculate size
        valid_mask = df["_has_bubble"]
        df["size"] = 150.0  # default size for hollow rings (float to avoid dtype warning)
        if valid_mask.any():
            valid_bubbles = df.loc[valid_mask, bubble_col]
            base_sizes = 100 + 900 * (
                np.log1p(valid_bubbles) / np.log1p(valid_bubbles.max())
            )
            df.loc[valid_mask, "size"] = (base_sizes * float(bubble_scale)).astype(float)
    else:
        # uniform bubble size, all filled
        df["size"] = 200
        df["_has_bubble"] = True

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

            # top by growth (or specified y_col)
            sort_col = y_col if y_col in q_data.columns else "Random_Slope"
            top_growth = q_data.nlargest(top_n_labels, sort_col).index.tolist()
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

    # define colors for each quadrant (tab20 - distinct hues)
    colors = {
        "Q1": "#d62728",  # top-right quadrant
        "Q2": "#ff7f0e",  # top-left quadrant
        "Q4": "#1f77b4",  # bottom-right quadrant
        "Q3": "#2ca02c",  # bottom-left quadrant
    }
    # Labels used in quadrant descriptions. If custom axis labels are
    # provided, reuse them; otherwise default to generic Volume/Growth
    # wording for backward compatibility.
    quadrant_x_label = x_label or "Volume"
    quadrant_y_label = y_label or "Growth"
    quadrant_display = {
        q: get_quadrant_label(q, x_label=quadrant_x_label, y_label=quadrant_y_label)
        for q in ["Q1", "Q2", "Q3", "Q4"]
    }

    # plot all points - filled for valid bubbles, hollow rings for null/0
    for q, color in colors.items():
        q_data = df[df["quadrant"] == q]
        if not q_data.empty:
            # Points with valid bubble values - filled circles
            filled = q_data[q_data["_has_bubble"]]
            if not filled.empty:
                plt.scatter(
                    filled[x_col],
                    filled[y_col],
                    s=filled["size"],
                    color=color,
                    alpha=0.7,
                    label=f"Q{q[-1]}",
                    zorder=2,
                )
            
            # Points with null/0 bubble values - hollow rings
            hollow = q_data[~q_data["_has_bubble"]]
            if not hollow.empty:
                plt.scatter(
                    hollow[x_col],
                    hollow[y_col],
                    s=hollow["size"],
                    facecolors="none",  # hollow
                    edgecolors=color,
                    linewidths=1.5,
                    alpha=0.7,
                    label=f"Q{q[-1]} (no data)" if filled.empty else None,
                    zorder=2,
                )

    # add axis lines
    plt.axhline(0, color="grey", linestyle="--", alpha=0.7, linewidth=1)
    plt.axvline(0, color="grey", linestyle="--", alpha=0.7, linewidth=1)

    # get current axis
    ax = plt.gca()

    # add quadrant labels as background text
    if show_quadrant_labels:
        # Use axes coordinates so labels stay centered even if x/y ranges are skewed.
        # Also offset the quadrant that would be covered by the legend.
        quadrant_centers_axes = {
            "Q1": (0.78, 0.78),
            "Q2": (0.22, 0.78),
            "Q3": (0.22, 0.22),
            "Q4": (0.78, 0.22),
        }

        # Only offset quadrant labels to avoid the legend when the legend is
        # actually being rendered.
        if show_legend:
            legend_loc_norm = str(legend_loc).strip().lower()
            if legend_loc_norm in {"lower right", "lower-right", "bottom right", "bottom-right"}:
                quadrant_centers_axes["Q4"] = (0.60, 0.18)
            elif legend_loc_norm in {"lower left", "lower-left", "bottom left", "bottom-left"}:
                quadrant_centers_axes["Q3"] = (0.40, 0.18)
            elif legend_loc_norm in {"upper left", "upper-left", "top left", "top-left"}:
                quadrant_centers_axes["Q2"] = (0.40, 0.82)
            elif legend_loc_norm in {"upper right", "upper-right", "top right", "top-right"}:
                quadrant_centers_axes["Q1"] = (0.60, 0.82)

        code_fontsize = max(1, int(quadrant_label_fontsize) + int(quadrant_code_fontsize_delta))

        for q, (cx, cy) in quadrant_centers_axes.items():
            label = quadrant_display[q]
            # Split into a large quadrant code + smaller description to make the
            # numbering easier to read (Q1 is top-right, then counter-clockwise).
            desc = label
            if label.startswith(f"{q} "):
                desc = label[len(q) + 1 :]

            bbox = {
                "facecolor": "white",
                "alpha": 0.35,
                "edgecolor": "none",
                "boxstyle": "round,pad=0.2",
            }

            # Render as two lines (Q# on top, description below) with tight
            # spacing. Use a single bbox behind both lines to avoid the visual
            # impression of a blank line (two separate bboxes create a gap).
            dy = 0.0

            # Invisible sizing text draws the single shared bbox.
            ax.text(
                cx,
                cy,
                f"{q}\n{desc}",
                transform=ax.transAxes,
                ha="center",
                va="center",
                fontsize=quadrant_label_fontsize,
                color="dimgray",
                alpha=0.0,
                zorder=4,
                fontweight="bold",
                bbox=bbox,
                linespacing=0.8,
            )

            ax.text(
                cx,
                cy + dy,
                q,
                transform=ax.transAxes,
                ha="center",
                va="bottom",
                fontsize=code_fontsize,
                color="dimgray",
                alpha=0.85,
                zorder=5,
                fontweight="bold",
            )
            ax.text(
                cx,
                cy - dy,
                desc,
                transform=ax.transAxes,
                ha="center",
                va="top",
                fontsize=quadrant_label_fontsize,
                color="dimgray",
                alpha=0.75,
                zorder=5,
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
                    row[x_col],
                    row[y_col],
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
    tick_fontsize = 15
    ax.tick_params(axis="both", which="major", labelsize=tick_fontsize)

    # create legend with equal-sized bubbles (order: Q1, Q2, Q3, Q4)
    legend_elements = []
    for q in ["Q1", "Q2", "Q3", "Q4"]:
        color = colors[q]
        legend_elements.append(
            Line2D(
                [0],
                [0],
                marker="o",
                color="w",
                markerfacecolor=color,
                markersize=10,
                label=quadrant_display[q],
            )
        )

    # set labels
    axis_fontsize = 15
    default_x_axis = "Volume (Relative)"
    default_y_axis = "Growth Rate (Relative)"
    plt.xlabel(x_label or default_x_axis, fontsize=axis_fontsize)
    plt.ylabel(y_label or default_y_axis, fontsize=axis_fontsize)

    # add title if provided
    if title is None:
        pretty_name = entity_name.strip()
        if "_" in pretty_name:
            pretty_name = pretty_name.replace("_", " ").title()
        title = f"{pretty_name} Priority Matrix"
    plt.title(title, fontsize=17, fontweight="bold", pad=20)

    # place legend
    if show_legend:
        legend_fontsize = 15
        plt.legend(
            handles=legend_elements,
            loc=legend_loc,
            frameon=False,
            title="Quadrants",
            fontsize=legend_fontsize,
            title_fontsize=legend_fontsize,
        )

    # remove chart borders
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_visible(False)
    ax.spines["bottom"].set_visible(False)

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

        os.makedirs(plot_dir, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d")
        granularity_suffix = {
            "quarterly": "Q",
            "yearly": "Y",
            "semiannual": "S",
            "monthly": "M",
        }.get(temporal_granularity, "Q")
        save_path = f"{plot_dir}/priority_matrix-{entity_name.lower()}-{granularity_suffix}-{timestamp}.png"

        plt.savefig(save_path, dpi=300, bbox_inches="tight", format="png")
        print(f"Plot saved: {save_path}")

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
        csv_path = f"{csv_dir}/priority_matrix-{entity_name.lower()}-{granularity_suffix}-{timestamp}.csv"

        # save key columns, plus any custom X/Y columns if present
        cols_to_save = [
            "entity",
            "quadrant",
            "x_score",
            "y_score",
            "count",
        ]
        for col in {x_col, y_col}:
            if col not in cols_to_save:
                cols_to_save.append(col)

        df[[c for c in cols_to_save if c in df.columns]].to_csv(csv_path, index=False)
        print(f"CSV saved: {csv_path}")

    fig = plt.gcf()
    if close_fig:
        plt.close(fig)
    return fig
