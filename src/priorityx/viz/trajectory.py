"""Entity movement trajectory plots."""

from typing import List, Optional, Tuple

import matplotlib.pyplot as plt
import pandas as pd


def plot_movement_trajectories(
    movement_df: pd.DataFrame,
    entity_name: str = "Entity",
    highlight_entities: Optional[List[str]] = None,
    max_entities: int = 10,
    figsize: Tuple[int, int] = (14, 10),
    title: Optional[str] = None,
    save_plot: bool = True,
    output_dir: str = "plot",
    temporal_granularity: str = "quarterly",
) -> plt.Figure:
    """
    Visualize entity trajectories through priority space.

    Shows how entities move through (X, Y) coordinates over time,
    with arrows indicating direction and markers for start/end points.

    Args:
        movement_df: DataFrame from track_cumulative_movement()
                    Required columns: entity, quarter, period_x, period_y,
                    period_quadrant, global_quadrant
        entity_name: Name for entity type (default: "Entity")
        highlight_entities: Specific entities to highlight (default: None = auto-select)
        max_entities: Maximum entities to show (default: 10)
        figsize: Figure size (width, height)
        title: Optional custom title
        save_plot: Save plot to file
        output_dir: Output directory for saved files
        temporal_granularity: Time granularity for file naming

    Returns:
        Matplotlib figure

    Examples:
        >>> # auto-select top movers
        >>> fig = plot_movement_trajectories(movement_df, entity_name="Service")

        >>> # highlight specific entities
        >>> fig = plot_movement_trajectories(
        ...     movement_df,
        ...     highlight_entities=["Service A", "Service B"],
        ...     max_entities=5
        ... )
    """
    if movement_df.empty:
        print("No movement data to visualize")
        return None

    # select entities to plot
    if highlight_entities:
        entities_to_plot = [
            e for e in highlight_entities if e in movement_df["entity"].values
        ]
    else:
        # select entities with largest movements
        entity_movement = movement_df.groupby("entity").agg({
            "x_delta": lambda x: abs(x).sum(),
            "y_delta": lambda x: abs(x).sum(),
        })
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

    # define colors for quadrants
    colors = {
        "Q1": "#c2104b",  # red - crisis
        "Q2": "#FF9636",  # orange - investigate
        "Q3": "#5cb85c",  # green - monitor
        "Q4": "#792f88",  # purple - low priority
    }

    # plot trajectories for each entity
    for entity in entities_to_plot:
        entity_data = df_plot[df_plot["entity"] == entity].sort_values("quarter")

        if len(entity_data) < 2:
            continue

        # get trajectory coordinates
        x = entity_data["period_x"].values
        y = entity_data["period_y"].values

        # get color from global quadrant
        global_quad = entity_data.iloc[0]["global_quadrant"]
        color = colors.get(global_quad, "#95a5a6")

        # plot trajectory line
        ax.plot(x, y, color=color, alpha=0.5, linewidth=2, zorder=1)

        # add arrows
        for i in range(len(x) - 1):
            dx = x[i + 1] - x[i]
            dy = y[i + 1] - y[i]
            ax.arrow(
                x[i], y[i], dx * 0.9, dy * 0.9,
                head_width=0.1,
                head_length=0.1,
                fc=color,
                ec=color,
                alpha=0.6,
                zorder=2,
            )

        # mark start point (circle)
        ax.scatter(
            x[0], y[0],
            s=150,
            c=color,
            marker='o',
            edgecolors='black',
            linewidth=2,
            alpha=0.8,
            zorder=3,
        )

        # mark end point (square)
        ax.scatter(
            x[-1], y[-1],
            s=150,
            c=color,
            marker='s',
            edgecolors='black',
            linewidth=2,
            alpha=0.8,
            zorder=3,
        )

        # add entity label at end point
        ax.annotate(
            entity,
            (x[-1], y[-1]),
            xytext=(5, 5),
            textcoords="offset points",
            fontsize=10,
            color=color,
            fontweight='bold',
            alpha=0.9,
        )

    # add quadrant dividers
    ax.axhline(0, color='grey', linestyle='--', alpha=0.7, linewidth=1, zorder=0)
    ax.axvline(0, color='grey', linestyle='--', alpha=0.7, linewidth=1, zorder=0)

    # add quadrant labels
    xlim = ax.get_xlim()
    ylim = ax.get_ylim()

    quadrant_labels = {
        "Q1": ("Q1: Crisis", (xlim[1] * 0.9, ylim[1] * 0.9)),
        "Q2": ("Q2: Investigate", (xlim[0] * 0.9, ylim[1] * 0.9)),
        "Q3": ("Q3: Monitor", (xlim[0] * 0.9, ylim[0] * 0.9)),
        "Q4": ("Q4: Low Priority", (xlim[1] * 0.9, ylim[0] * 0.9)),
    }

    for label, (x_pos, y_pos) in quadrant_labels.values():
        ax.text(
            x_pos, y_pos,
            label,
            ha="center",
            va="center",
            fontsize=12,
            color="gray",
            alpha=0.3,
            fontweight="bold",
            zorder=0,
        )

    # set labels
    ax.set_xlabel(f"{entity_name} Volume (Relative)", fontsize=13)
    ax.set_ylabel(f"{entity_name} Growth Rate (Relative)", fontsize=13)

    if title:
        ax.set_title(title, fontsize=16, fontweight="bold", pad=20)
    else:
        ax.set_title(f"{entity_name} Movement Trajectories", fontsize=16,
                    fontweight="bold", pad=20)

    # add legend for markers
    from matplotlib.lines import Line2D
    marker_legend = [
        Line2D([0], [0], marker='o', color='w', markerfacecolor='gray',
               markersize=10, label='Start', markeredgecolor='black', markeredgewidth=2),
        Line2D([0], [0], marker='s', color='w', markerfacecolor='gray',
               markersize=10, label='End', markeredgecolor='black', markeredgewidth=2),
    ]
    ax.legend(
        handles=marker_legend,
        loc='upper left',
        frameon=False,
        fontsize=10,
    )

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
        plot_path = f"{output_dir}/cumulative_movement-{entity_name.lower()}-{granularity_suffix}-{timestamp}.png"
        plt.savefig(plot_path, dpi=300, bbox_inches="tight", format="png")
        print(f"Movement plot saved: {plot_path}")

    return fig
