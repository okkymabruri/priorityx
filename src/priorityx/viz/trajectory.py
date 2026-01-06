"""Entity movement trajectory plots."""

from typing import List, Optional, Tuple
import warnings

import matplotlib.pyplot as plt
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
    temporal_granularity: str = "quarterly",
    close_fig: bool = False,
) -> plt.Figure:
    """
    Visualize entity trajectories through priority space.

    Shows cumulative entity trajectories over time using quarterly markers,
    displaying how entities move through priority quadrants.

    Args:
        movement_df: DataFrame from track_cumulative_movement()
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

    # select entities to plot
    if highlight_entities:
        entities_to_plot = [
            e for e in highlight_entities if e in movement_df["entity"].values
        ]
    else:
        # select entities with largest movements
        entity_movement = movement_df.groupby("entity").agg(
            {
                "x_delta": lambda x: abs(x).sum(),
                "y_delta": lambda x: abs(x).sum(),
            }
        )
        entity_movement["total_movement"] = (
            entity_movement["x_delta"] + entity_movement["y_delta"]
        )
        top_movers = entity_movement.nlargest(max_entities, "total_movement")
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

    # add quadrant labels
    xlim = ax.get_xlim()
    ylim = ax.get_ylim()

    quadrant_positions = {
        "Q1": (xlim[1] * 0.85, ylim[1] * 0.85),
        "Q2": (xlim[0] * 0.85, ylim[1] * 0.85),
        "Q3": (xlim[0] * 0.85, ylim[0] * 0.85),
        "Q4": (xlim[1] * 0.85, ylim[0] * 0.85),
    }

    for quadrant, (x_pos, y_pos) in quadrant_positions.items():
        ax.text(
            x_pos,
            y_pos,
            quadrant_display[quadrant],
            ha="center",
            va="center",
            fontsize=15,
            color="gray",
            alpha=0.3,
            fontweight="bold",
            zorder=0,
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
        loc="upper left",
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
        timestamp = datetime.now().strftime("%Y%m%d")
        granularity_suffix = {
            "quarterly": "Q",
            "yearly": "Y",
            "semiannual": "S",
            "monthly": "M",
        }.get(temporal_granularity, "Q")
        plot_path = f"{plot_dir}/trajectories-{entity_name.lower()}-{granularity_suffix}-{timestamp}.png"
        plt.savefig(plot_path, dpi=300, bbox_inches="tight", format="png")
        print(f"Entity trajectory plot saved: {plot_path}")

    if save_csv:
        # Only save the trajectories actually plotted (df_plot), not the
        # full movement_df. The full movement data remains available in
        # the movement CSVs.
        target_dir = csv_dir if csv_dir else f"{plot_dir}/../results"
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
