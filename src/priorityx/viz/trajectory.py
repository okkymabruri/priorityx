"""Entity movement trajectory plots."""

from typing import List, Optional, Tuple
import warnings

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from priorityx.core.quadrants import get_quadrant_label
from priorityx.utils.helpers import save_dataframe_to_csv

# suppress noisy FancyArrowPatch fallback warnings from annotate/adjustments
warnings.filterwarnings(
    "ignore",
    message=".*FancyArrowPatch.*",
    category=UserWarning,
)


def plot_entity_trajectories(
    movement_df: pd.DataFrame,
    entity_name: str = "Entity",
    highlight_entities: Optional[List[str]] = None,
    max_entities: int = 10,
    figsize: Tuple[int, int] = (16, 12),
    title: Optional[str] = None,
    save_plot: bool = False,
    save_csv: bool = False,
    plot_dir: str = "results/plot",
    csv_dir: Optional[str] = "results/csv",
    plot_filename: Optional[str] = None,
    csv_filename: Optional[str] = None,
    temporal_granularity: str = "quarterly",
    close_fig: bool = False,
    legend_loc: str = "lower right",
    show_legend: bool = True,
    highlight_top_n: Optional[int] = None,
    highlight_by: str = "trajectory_distance",
    recent_periods: Optional[int] = None,
) -> plt.Figure:
    """
    Visualize entity trajectories through priority space.

    Shows cumulative entity trajectories over time using quarterly markers,
    displaying how entities move through priority quadrants.

    Args:
        movement_df: DataFrame from track_movement()
                    Required columns: entity, quarter, period_x, period_y,
                    global_quadrant
        entity_name: Name for entity type (default: "Entity")
        highlight_entities: Specific entities to highlight (default: None = auto-select)
        max_entities: Maximum entities to show (default: 10)
        figsize: Figure size (width, height)
        title: Optional custom title
        save_plot: Save plot to file (default: False)
        save_csv: Save trajectories to CSV (default: False)
        plot_dir: Output directory for plot files
        csv_dir: Output directory for CSV files
        temporal_granularity: Time granularity for file naming
        close_fig: Close the figure before returning (set True if you see duplicate inline renders)
        legend_loc: Legend position (default: "lower right")
        show_legend: Whether to show the quadrant legend (default: True)
        highlight_top_n: Auto-select top N entities (overrides max_entities when set)
        highlight_by: Selection method - "trajectory_distance" (euclidean path length)
                     or "total_movement" (sum of |x| + |y| deltas). Default: "trajectory_distance"
        recent_periods: Limit trajectory to last N periods (default: None = all periods)

    Returns:
        Matplotlib figure

    Examples:
        >>> # auto-select top movers
        >>> fig = plot_entity_trajectories(movement_df, entity_name="Service")

        >>> # highlight specific entities
        >>> fig = plot_entity_trajectories(
        ...     movement_df,
        ...     highlight_entities=["Service A", "Service B"],
        ...     max_entities=5
        ... )
    """
    if movement_df.empty:
        print("No movement data to visualize")
        return None

    period_col = "quarter"

    # trim trajectories after last period with new events
    if "period_count" in movement_df.columns:
        df_trim = movement_df.copy()
        active = df_trim[df_trim["period_count"].fillna(0) > 0]
        if not active.empty:
            last_active = active.groupby("entity")[period_col].max()
            df_trim = df_trim.merge(
                last_active.rename("last_active_quarter"),
                on="entity",
                how="left",
            )
            # keep only entities that ever had positive period_count
            # and cut them at their last active period
            df_trim = df_trim[
                df_trim["last_active_quarter"].notna()
                & (df_trim[period_col] <= df_trim["last_active_quarter"])
            ]
            movement_df = df_trim

    # apply recent_periods filter
    if recent_periods is not None and recent_periods > 0:
        all_periods = sorted(movement_df[period_col].astype(str).unique().tolist())
        if len(all_periods) > recent_periods:
            window_start = all_periods[-recent_periods]
            movement_df = movement_df[
                movement_df[period_col].astype(str) >= window_start
            ].copy()

    # select entities to plot
    n_to_select = highlight_top_n if highlight_top_n else max_entities

    if highlight_entities:
        entities_to_plot = [
            e for e in highlight_entities if e in movement_df["entity"].values
        ]
    elif highlight_top_n is not None and highlight_by == "trajectory_distance":
        # calculate trajectory distance (euclidean path length)
        df_sorted = movement_df.sort_values(["entity", period_col]).copy()
        df_sorted["period_x"] = pd.to_numeric(df_sorted.get("period_x"), errors="coerce")
        df_sorted["period_y"] = pd.to_numeric(df_sorted.get("period_y"), errors="coerce")
        df_sorted["dx"] = df_sorted.groupby("entity")["period_x"].diff()
        df_sorted["dy"] = df_sorted.groupby("entity")["period_y"].diff()
        df_sorted["step_distance"] = np.sqrt(
            df_sorted["dx"] ** 2 + df_sorted["dy"] ** 2
        ).fillna(0)

        dist_by_entity = (
            df_sorted.groupby("entity", as_index=False)["step_distance"]
            .sum()
            .rename(columns={"step_distance": "trajectory_distance"})
        )

        # get volume for tiebreaker
        vol_col = "cumulative_count" if "cumulative_count" in movement_df.columns else None
        if vol_col:
            last_period = movement_df.sort_values(period_col).groupby("entity").tail(1)
            last_period[vol_col] = pd.to_numeric(
                last_period.get(vol_col), errors="coerce"
            ).fillna(0)
            dist_by_entity = dist_by_entity.merge(
                last_period[["entity", vol_col]], on="entity", how="left"
            )
            dist_by_entity[vol_col] = dist_by_entity[vol_col].fillna(0)
            top_movers = dist_by_entity.sort_values(
                ["trajectory_distance", vol_col], ascending=[False, False]
            ).head(n_to_select)
        else:
            top_movers = dist_by_entity.nlargest(n_to_select, "trajectory_distance")

        entities_to_plot = top_movers["entity"].tolist()

        # fill with high-volume entities if not enough
        if len(entities_to_plot) < n_to_select and vol_col:
            remaining = dist_by_entity[
                ~dist_by_entity["entity"].isin(entities_to_plot)
            ].nlargest(n_to_select - len(entities_to_plot), vol_col)
            entities_to_plot.extend(remaining["entity"].tolist())
    else:
        # original logic: select entities with largest movements
        entity_movement = movement_df.groupby("entity").agg(
            {
                "x_delta": lambda x: abs(x).sum(),
                "y_delta": lambda x: abs(x).sum(),
            }
        )
        entity_movement["total_movement"] = (
            entity_movement["x_delta"] + entity_movement["y_delta"]
        )
        top_movers = entity_movement.nlargest(n_to_select, "total_movement")
        entities_to_plot = top_movers.index.tolist()

    # filter movement data
    df_plot = movement_df[movement_df["entity"].isin(entities_to_plot)].copy()

    if df_plot.empty:
        print("No entities to plot")
        return None

    # create figure
    fig, ax = plt.subplots(figsize=figsize)

    # define colors for quadrants (tab20 - distinct hues)
    colors = {
        "Q1": "#d62728",  # top-right quadrant
        "Q2": "#ff7f0e",  # top-left quadrant
        "Q4": "#1f77b4",  # bottom-right quadrant
        "Q3": "#2ca02c",  # bottom-left quadrant
    }
    quadrant_display = {
        q: get_quadrant_label(q, x_label="Volume", y_label="Growth")
        for q in ["Q1", "Q2", "Q3", "Q4"]
    }

    # track usage counts per color to slightly vary hue if needed
    used_colors = {}

    # plot trajectories for each entity
    for entity in entities_to_plot:
        entity_data = df_plot[df_plot["entity"] == entity].sort_values(period_col)

        if len(entity_data) < 2:
            continue

        # use period coordinates for cumulative trajectory
        x = entity_data["period_x"].values
        y = entity_data["period_y"].values
        quarters = entity_data[period_col].values

        # get color from global quadrant
        global_quad = entity_data.iloc[0]["global_quadrant"]

        # find alternative color if already used
        base_color = colors.get(global_quad, "#95a5a6")
        color = base_color

        used_colors[base_color] = used_colors.get(base_color, 0) + 1
        if used_colors[base_color] > 1:
            # generate darker shade for same quadrant (better contrast)
            if base_color == "#d62728":  # Q1 red
                color = "#cc0000"  # darker red
            elif base_color == "#ff7f0e":  # Q2 orange
                color = "#cc6600"  # darker orange
            elif base_color == "#1f77b4":  # Q4 blue
                color = "#0066cc"  # darker blue
            elif base_color == "#2ca02c":  # Q3 green
                color = "#006600"  # darker green
        else:
            color = base_color

        # plot smooth trajectory line
        ax.plot(x, y, color=color, alpha=0.6, linewidth=2, zorder=1)

        # plot quarterly markers with unique shapes for overlapping entities
        ax.scatter(
            x,
            y,
            s=90,
            c=color,
            marker="o",
            edgecolors="white",
            linewidth=1.5,
            alpha=0.9,
            zorder=3,
        )

        # add quarter labels on first and last points
        ax.annotate(
            quarters[0],
            (x[0], y[0]),
            xytext=(0, 8),
            textcoords="offset points",
            fontsize=10,
            color="black",
            ha="center",
            alpha=0.8,
        )

        ax.annotate(
            quarters[-1],
            (x[-1], y[-1]),
            xytext=(0, 8),
            textcoords="offset points",
            fontsize=10,
            color="black",
            ha="center",
            alpha=0.8,
        )

        ax.annotate(
            entity,
            (x[-1], y[-1]),
            xytext=(8, -8),
            textcoords="offset points",
            fontsize=10,
            color="black",
            alpha=0.9,
        )

    # quadrant dividers will be added later with improved styling

    # add quadrant labels using axes transform (fixed position like matrix.py)
    quadrant_centers_axes = {
        "Q1": (0.78, 0.78),
        "Q2": (0.22, 0.78),
        "Q3": (0.22, 0.22),
        "Q4": (0.78, 0.22),
    }

    # offset quadrant labels to avoid legend overlap (move both labels in same row together)
    if show_legend:
        legend_loc_norm = str(legend_loc).strip().lower()
        if legend_loc_norm in {"lower right", "lower-right", "bottom right", "bottom-right"}:
            # move both bottom labels up together to stay aligned
            quadrant_centers_axes["Q3"] = (0.22, 0.35)
            quadrant_centers_axes["Q4"] = (0.78, 0.35)
        elif legend_loc_norm in {"lower left", "lower-left", "bottom left", "bottom-left"}:
            # move both bottom labels up together to stay aligned
            quadrant_centers_axes["Q3"] = (0.22, 0.35)
            quadrant_centers_axes["Q4"] = (0.78, 0.35)
        elif legend_loc_norm in {"upper left", "upper-left", "top left", "top-left"}:
            # move both top labels down together to stay aligned
            quadrant_centers_axes["Q1"] = (0.78, 0.65)
            quadrant_centers_axes["Q2"] = (0.22, 0.65)
        elif legend_loc_norm in {"upper right", "upper-right", "top right", "top-right"}:
            # move both top labels down together to stay aligned
            quadrant_centers_axes["Q1"] = (0.78, 0.65)
            quadrant_centers_axes["Q2"] = (0.22, 0.65)

    quadrant_label_fontsize = 15
    quadrant_code_fontsize = 21  # larger for Q# code

    for quadrant, (cx, cy) in quadrant_centers_axes.items():
        label = quadrant_display[quadrant]
        # split into Q# code and description
        desc = label
        if label.startswith(f"{quadrant} "):
            desc = label[len(quadrant) + 1:]

        bbox = {
            "facecolor": "white",
            "alpha": 0.35,
            "edgecolor": "none",
            "boxstyle": "round,pad=0.2",
        }

        # invisible sizing text for shared bbox
        ax.text(
            cx,
            cy,
            f"{quadrant}\n{desc}",
            transform=ax.transAxes,
            ha="center",
            va="center",
            fontsize=quadrant_label_fontsize,
            color="dimgray",
            alpha=0.0,
            zorder=0,
            fontweight="bold",
            bbox=bbox,
            linespacing=0.8,
        )

        # Q# code (larger)
        ax.text(
            cx,
            cy,
            quadrant,
            transform=ax.transAxes,
            ha="center",
            va="bottom",
            fontsize=quadrant_code_fontsize,
            color="dimgray",
            alpha=0.85,
            zorder=1,
            fontweight="bold",
        )
        # description (smaller)
        ax.text(
            cx,
            cy,
            desc,
            transform=ax.transAxes,
            ha="center",
            va="top",
            fontsize=quadrant_label_fontsize,
            color="dimgray",
            alpha=0.75,
            zorder=1,
            fontweight="bold",
        )

    # set labels - use readable names
    axis_fontsize = 15
    if "fsp" in entity_name.lower():
        ylabel = "FSP"
    elif "topic" in entity_name.lower():
        ylabel = "Topic"
    elif "product" in entity_name.lower():
        ylabel = "Product"
    else:
        ylabel = entity_name
    ax.set_xlabel("Volume (Relative)", fontsize=axis_fontsize)
    ax.set_ylabel("Growth Rate (Relative)", fontsize=axis_fontsize)

    # Only set title if not empty string
    if title is None:
        title = f"{ylabel} Entity Trajectory"
    if title:  # Skip if empty string
        ax.set_title(title, fontsize=17, fontweight="bold", pad=20)

    # add legend for quadrants
    if show_legend:
        from matplotlib.lines import Line2D

        quadrant_legend = [
            Line2D(
                [0],
                [0],
                color=colors[quadrant],
                linewidth=3,
                label=quadrant_display[quadrant],
            )
            for quadrant in ["Q1", "Q2", "Q3", "Q4"]
        ]
        legend_fontsize = 15
        ax.legend(
            handles=quadrant_legend,
            loc=legend_loc,
            frameon=False,
            fontsize=legend_fontsize,
            title="Quadrants",
            title_fontsize=legend_fontsize,
        )

    # remove plot borders for cleaner look
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["bottom"].set_visible(False)
    ax.spines["left"].set_visible(False)

    # keep quadrant dividers but make them more subtle
    ax.axhline(0, color="grey", linestyle="--", alpha=0.7, linewidth=1, zorder=0)
    ax.axvline(0, color="grey", linestyle="--", alpha=0.7, linewidth=1, zorder=0)

    tick_fontsize = 15
    ax.tick_params(axis="both", which="major", labelsize=tick_fontsize)

    plt.tight_layout()

    # save plot if requested
    if save_plot:
        import os
        from datetime import datetime

        os.makedirs(plot_dir, exist_ok=True)
        if plot_filename:
            plot_path = os.path.join(plot_dir, plot_filename)
            if not plot_path.lower().endswith(".png"):
                plot_path = f"{plot_path}.png"
        else:
            timestamp = datetime.now().strftime("%Y%m%d")
            granularity_suffix = {
                "quarterly": "Q",
                "yearly": "Y",
                "semiannual": "S",
                "monthly": "M",
            }.get(temporal_granularity, "Q")
            entity_slug = entity_name.lower().replace(" ", "_")
            plot_path = f"{plot_dir}/trajectories-{entity_slug}-{granularity_suffix}-{timestamp}.png"
        plt.savefig(plot_path, dpi=300, bbox_inches="tight", format="png")
        print(f"Entity trajectory plot saved: {plot_path}")

    if save_csv:
        # Only save the trajectories actually plotted (df_plot), not the
        # full movement_df. The full movement data remains available in
        # the movement CSVs.
        target_dir = csv_dir if csv_dir else f"{plot_dir}/../results"
        if csv_filename:
            os.makedirs(target_dir, exist_ok=True)
            csv_path = os.path.join(target_dir, csv_filename)
            if not csv_path.lower().endswith(".csv"):
                csv_path = f"{csv_path}.csv"
            df_plot.to_csv(csv_path, index=False)
        else:
            csv_path = save_dataframe_to_csv(
                df_plot,
                artifact="trajectories",
                entity_name=entity_name,
                temporal_granularity=temporal_granularity,
                output_dir=target_dir,
            )
        print(f"Trajectories CSV saved: {csv_path}")

    if close_fig:
        plt.close(fig)

    return fig
