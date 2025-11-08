"""Entity movement trajectory plots."""

from typing import List, Optional, Tuple

import matplotlib.pyplot as plt
import pandas as pd


def plot_entity_trajectories(
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
        save_plot: Save plot to file
        output_dir: Output directory for saved files
        temporal_granularity: Time granularity for file naming

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
        "Q1": "#d62728",  # tab red - critical
        "Q2": "#ff7f0e",  # tab orange - investigate
        "Q4": "#1f77b4",  # tab blue - low priority
        "Q3": "#2ca02c",  # tab green - monitor
    }

    # plot trajectories for each entity
    for entity in entities_to_plot:
        entity_data = df_plot[df_plot["entity"] == entity].sort_values("quarter")

        if len(entity_data) < 2:
            continue

        # use period coordinates for cumulative trajectory
        x = entity_data["period_x"].values
        y = entity_data["period_y"].values
        quarters = entity_data["quarter"].values

        # get color from global quadrant
        global_quad = entity_data.iloc[0]["global_quadrant"]
        color = colors.get(global_quad, "#95a5a6")

        # plot smooth trajectory line
        ax.plot(x, y, color=color, alpha=0.6, linewidth=2, zorder=1)

        # plot quarterly markers
        ax.scatter(
            x,
            y,
            s=80,
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
            fontsize=8,
            color=color,
            ha="center",
            alpha=0.8,
        )

        ax.annotate(
            quarters[-1],
            (x[-1], y[-1]),
            xytext=(0, 8),
            textcoords="offset points",
            fontsize=8,
            color=color,
            ha="center",
            alpha=0.8,
        )

        # add entity label at end point
        ax.annotate(
            entity,
            (x[-1], y[-1]),
            xytext=(8, -8),
            textcoords="offset points",
            fontsize=10,
            color=color,
            fontweight="bold",
            alpha=0.9,
            bbox=dict(boxstyle="round,pad=0.3", facecolor="white", edgecolor=color, alpha=0.7),
        )

    # add quadrant dividers
    ax.axhline(0, color="grey", linestyle="--", alpha=0.7, linewidth=1, zorder=0)
    ax.axvline(0, color="grey", linestyle="--", alpha=0.7, linewidth=1, zorder=0)

    # add quadrant labels
    xlim = ax.get_xlim()
    ylim = ax.get_ylim()

    quadrant_labels = {
        "Q1": ("Q1\nCritical", (xlim[1] * 0.85, ylim[1] * 0.85)),
        "Q2": ("Q2\nEmerging", (xlim[0] * 0.85, ylim[1] * 0.85)),
        "Q3": ("Q3\nLow Priority", (xlim[0] * 0.85, ylim[0] * 0.85)),
        "Q4": ("Q4\nPersistent", (xlim[1] * 0.85, ylim[0] * 0.85)),
    }

    for label, (x_pos, y_pos) in quadrant_labels.values():
        ax.text(
            x_pos,
            y_pos,
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
    ax.set_xlabel("X-axis: Volume (Random Intercept)", fontsize=13)
    ax.set_ylabel("Y-axis: Growth Rate (Random Slope)", fontsize=13)

    if title:
        ax.set_title(title, fontsize=16, fontweight="bold", pad=20)
    else:
        ax.set_title(
            f"{entity_name} Entity Trajectory",
            fontsize=16,
            fontweight="bold",
            pad=20,
        )

    # add legend for quadrants
    from matplotlib.lines import Line2D

    quadrant_legend = [
        Line2D([0], [0], color=colors["Q1"], linewidth=3, label="Q1 (Global)"),
        Line2D([0], [0], color=colors["Q2"], linewidth=3, label="Q2 (Global)"),
        Line2D([0], [0], color=colors["Q3"], linewidth=3, label="Q3 (Global)"),
        Line2D([0], [0], color=colors["Q4"], linewidth=3, label="Q4 (Global)"),
    ]
    ax.legend(
        handles=quadrant_legend,
        loc="upper left",
        frameon=False,
        fontsize=10,
        title="Quadrants",
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
