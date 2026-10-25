"""Transition timeline heatmap visualization."""

from math import sqrt
from pathlib import Path
from typing import List, Literal, Optional, Tuple, Union
import warnings

import matplotlib.pyplot as plt
from matplotlib.collections import PathCollection
from matplotlib.offsetbox import AnnotationBbox, DrawingArea, HPacker, TextArea, VPacker
from matplotlib.patches import Circle
from matplotlib.path import Path as RenderPath
from matplotlib.text import Annotation, Text
from matplotlib.transforms import Bbox
import pandas as pd

from priorityx.i18n import text as translate, validate_language
from priorityx.tracking.transitions import classify_priority

# suppress noisy FancyArrowPatch fallback warnings from annotate/adjustments
warnings.filterwarnings(
    "ignore",
    message=".*FancyArrowPatch.*",
    category=UserWarning,
)


class TransitionLabelLayoutWarning(UserWarning):
    """Placement did not resolve every event label at the requested size."""


def _marker_boxes(ax, points_to_pixels):
    """Measure scatter markers, including their stroke, in display coordinates."""
    boxes = []
    for collection in ax.collections:
        if not isinstance(collection, PathCollection) or not collection.get_visible():
            continue
        sizes = collection.get_sizes()
        paths = collection.get_paths()
        widths = collection.get_linewidths()
        if not len(sizes) or not paths:
            continue
        offsets = collection.get_offset_transform().transform(collection.get_offsets())
        for index, (x, y) in enumerate(offsets):
            extent = paths[index % len(paths)].get_extents()
            scale = sqrt(sizes[index % len(sizes)]) * points_to_pixels
            stroke = widths[index % len(widths)] * points_to_pixels / 2 if len(widths) else 0
            boxes.append(Bbox.from_extents(
                x + extent.x0 * scale - stroke, y + extent.y0 * scale - stroke,
                x + extent.x1 * scale + stroke, y + extent.y1 * scale + stroke,
            ))
    return boxes


def _leader_segment(anchor, box):
    """Connect the event to the nearest edge of its label."""
    return RenderPath([anchor, (
        min(max(anchor[0], box.x0), box.x1),
        min(max(anchor[1], box.y0), box.y1),
    )])


def _make_transition_key(ax, example, language="en"):
    """Explain compact notation using one displayed event, without extra data marks."""
    source, destination, suffix, color = example

    def text(value, *, bold=False):
        return TextArea(value, textprops={"fontsize": 12,
                                         "fontweight": "bold" if bold else "normal"})

    marker = DrawingArea(18, 18)
    marker.add_artist(Circle((9, 9), 7, facecolor=color, edgecolor=color, alpha=0.8))
    marker.add_artist(Text(9, 9, destination, fontsize=12, ha="center", va="center"))
    token = HPacker(children=[text(f"{source}→"), marker, text(suffix)],
                    align="center", pad=0, sep=1)
    before = VPacker(children=[
        text(translate(language, "read_event"), bold=True), token,
        text(f"{translate(language, 'event_from_to', source=source, destination=destination)}\n"
             f"{translate(language, 'event_digit')}\n"
             f"{translate(language, 'event_color')}\n{translate(language, 'event_suffix')}"),
    ], align="left", pad=0, sep=6)
    after = VPacker(children=[
        text(translate(language, "suffix"), bold=True),
        text(f"*$^X$    {translate(language, 'x_spike')}\n"
             f"*$^Y$    {translate(language, 'y_spike')}\n"
             f"*$^{{XY}}$  {translate(language, 'both_axes')}"),
    ], align="left", pad=0, sep=6)
    for content in (before, after):
        panel = AnnotationBbox(content, (0, 0), xycoords=ax.figure.transFigure,
                               box_alignment=(0, 1), frameon=False, pad=0,
                               annotation_clip=False, gid="priorityx-transition-key")
        panel.set_in_layout(False)  # Positioned after the initial tight_layout.
        ax.add_artist(panel)


def _key_boxes(ax, renderer):
    return [artist.get_window_extent(renderer) for artist in ax.artists
            if artist.get_gid() == "priorityx-transition-key" and artist.get_visible()]


def _position_transition_key(ax, renderer, language="en"):
    """Fit the reading example and suffix key around the caller's final legend."""
    legend = ax.get_legend()
    if legend is None or not legend.get_visible():
        return
    panels = [artist for artist in ax.artists
              if artist.get_gid() == "priorityx-transition-key"]
    if not panels:
        return
    title = legend.get_title().get_text()
    if not title.startswith("Color · ") and not title.startswith("Warna · "):
        title = translate(language, "event_class")
        prefix = translate(language, "color")
        legend.set_title(f"{prefix} · {title}")
    legend.get_title().set_fontsize(12)
    legend.get_title().set_fontweight("bold")
    legend.set_alignment("left")
    for text in legend.get_texts():
        text.set_fontsize(12)

    # Save caller placement in axes coordinates; never accumulate our shift.
    anchor = tuple(legend.get_bbox_to_anchor().transformed(ax.transAxes.inverted()).bounds)
    previous = getattr(legend, "_priorityx_key_anchor", None)
    if previous is None or any(abs(a - b) > 1e-9 for a, b in zip(anchor, previous)):
        legend._priorityx_base_anchor = anchor
    anchor = legend._priorityx_base_anchor
    legend.set_bbox_to_anchor(anchor, transform=ax.transAxes)
    box = legend.get_window_extent(renderer)
    gap = renderer.points_to_pixels(12)
    inset = renderer.points_to_pixels(legend.borderpad * 12)
    # Figure fractions follow the translated origin during bbox_inches="tight".
    # Absolute figure pixels would leave the key behind and clip its right edge.
    to_figure = ax.figure.transFigure.inverted()
    panels[0].xy = panels[0].xybox = tuple(to_figure.transform((box.x0 + inset, box.y1)))
    panels[0].set_in_layout(True)
    panels[0].update_positions(renderer)
    shift = panels[0].get_window_extent(renderer).height + gap
    legend.set_bbox_to_anchor((anchor[0], anchor[1] - shift / ax.bbox.height,
                              anchor[2], anchor[3]), transform=ax.transAxes)
    legend._priorityx_key_anchor = tuple(
        legend.get_bbox_to_anchor().transformed(ax.transAxes.inverted()).bounds
    )
    box = legend.get_window_extent(renderer)
    panels[1].xy = panels[1].xybox = tuple(to_figure.transform((box.x0 + inset, box.y0 - gap)))
    panels[1].set_in_layout(True)
    panels[1].update_positions(renderer)


def _pad_compact_labels(ax, labels, renderer):
    """Reserve measured empty edge space without changing event dates or ticks."""
    current = ax.get_xlim()
    previous = getattr(ax, "_priorityx_padded_xlim", None)
    if previous is None or current != previous:
        ax._priorityx_base_xlim = current
    lo, hi = ax._priorityx_base_xlim
    unit = renderer.points_to_pixels(1)
    for _ in range(20):
        ax.set_xlim(lo, hi)
        # Refresh Annotation's offset transform after changing the data limits.
        for text in labels:
            text.update_positions(renderer)
        boxes = [Text.get_window_extent(text, renderer) for text in labels]
        left = max(0, ax.bbox.x0 + 2 * unit - min(box.x0 for box in boxes))
        right = max(0, max(box.x1 for box in boxes) - ax.bbox.x1 + 2 * unit)
        if max(left, right) < 0.01:
            break
        scale = (hi - lo) / ax.bbox.width
        lo, hi = lo - left * scale, hi + right * scale
    ax.set_xlim(lo, hi)
    ax._priorityx_padded_xlim = ax.get_xlim()


def _compact_collisions(ax, labels, renderer):
    """Count unreadable inline parts; retain them in place for explicit review."""
    unit = renderer.points_to_pixels(1)
    boxes = [Text.get_window_extent(text, renderer) for text in labels]
    markers = _marker_boxes(ax, unit)
    others = [Text.get_window_extent(text, renderer) for text in ax.texts
              if text.get_visible() and text not in labels
              and text.get_gid() != "priorityx-transition-destination"]
    legend = ax.get_legend()
    if legend and legend.get_visible():
        others.append(legend.get_window_extent(renderer))
    others += _key_boxes(ax, renderer)
    rows = sorted(ax.transData.transform((0, y))[1] for y in ax.get_yticks())
    unresolved = 0
    for index, (text, box) in enumerate(zip(labels, boxes)):
        anchor = ax.transData.transform(text.xy)
        row = min(range(len(rows)), key=lambda i: abs(rows[i] - anchor[1]))
        bottom = (rows[row - 1] + rows[row]) / 2 if row else ax.bbox.y0
        top = (rows[row] + rows[row + 1]) / 2 if row + 1 < len(rows) else ax.bbox.y1
        if (box.x0 < ax.bbox.x0 or box.x1 > ax.bbox.x1
                or box.y0 < max(bottom, ax.bbox.y0) or box.y1 > min(top, ax.bbox.y1)
                or any(box.overlaps(other) for i, other in enumerate(boxes) if i != index)
                or any(box.overlaps(other) for other in markers + others)):
            unresolved += 1
    return unresolved


def layout_transition_labels(fig: plt.Figure, language: str = "en") -> plt.Figure:
    """Place timeline text deterministically without moving event markers.

    Call again after changing titles, ticks, legends, figure size or DPI, and
    after any ``tight_layout()`` call. Only annotations created by
    :func:`plot_transition_timeline` are adjusted, at their existing font size. Compact
    labels stay horizontal: source → destination marker, then spike suffix.
    Measured empty edge padding keeps that order even at plot boundaries.
    Quadrant label centers stay nearest their entity's row; displaced labels
    receive leader lines. Both styles are checked
    against neighboring text, markers, legends and plot boundaries.
    The same figure is returned.

    If the available space cannot accommodate every label, all text is retained
    and a :class:`TransitionLabelLayoutWarning` recommends an explicit larger
    ``figsize`` or separate ``entity_filter`` pages. A warning means the chart
    still requires review; the helper never silently changes entity selection.
    """
    language = validate_language(language)
    # Reset first so repeated calls do not accumulate offsets or leader lines.
    for ax in fig.axes:
        for text in ax.texts:
            if isinstance(text, Annotation) and text.get_gid() == "priorityx-transition-label":
                parts = getattr(text, "_priorityx_compact_parts", None)
                if parts is not None:
                    source, _ = parts
                    text.set_text(f"{source}→")
                    text.set_ha("right")
                    suffix = text._priorityx_suffix
                    suffix.xy = text.xy
                    suffix.set_position((9, 0))
                    suffix.set_fontsize(text.get_fontsize())
                text.set_position((-9 if parts is not None else 8, 0))
                text.arrow_patch.set_visible(False)
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    for ax in fig.axes:
        inline = [text for text in ax.texts if isinstance(text, Annotation)
                  and text.get_visible() and (
                      hasattr(text, "_priorityx_compact_parts")
                      or text.get_gid() == "priorityx-transition-suffix")]
        if inline:
            _pad_compact_labels(ax, inline, renderer)
        _position_transition_key(ax, renderer, language)
    fig.canvas.draw()
    unit = renderer.points_to_pixels(1)
    # Keep a small measured clearance around text.  A larger fixed gap can
    # make otherwise solvable adjacent quarterly labels appear unresolved on
    # older supported Matplotlib renderers.
    padding = 1.0 * unit
    unresolved = 0
    overlapping_destinations = 0

    for ax in fig.axes:
        labels = [text for text in ax.texts
                  if isinstance(text, Annotation)
                  and text.get_gid() == "priorityx-transition-label"
                  and not hasattr(text, "_priorityx_compact_parts")]
        axes_box = ax.get_window_extent(renderer)
        rows = sorted(ax.transData.transform((0, y))[1] for y in ax.get_yticks())
        markers = _marker_boxes(ax, unit)
        destination_boxes = [Text.get_window_extent(text, renderer) for text in ax.texts
                             if text.get_gid() == "priorityx-transition-destination"]
        overlapping_destinations += sum(
            box.overlaps(other) for index, box in enumerate(destination_boxes)
            for other in destination_boxes[index + 1:]
        )
        legend = ax.get_legend()
        decorations = [legend.get_window_extent(renderer)] if legend and legend.get_visible() else []
        decorations += [text.get_window_extent(renderer) for text in ax.texts
                        if text not in labels and text.get_visible()
                        and text.get_gid() != "priorityx-transition-destination"]
        decorations += _key_boxes(ax, renderer)
        placed = []
        leaders = []

        # Reserve the constrained right edge first for full Q-style labels.
        for text in sorted(labels, key=lambda item: (item.xy[1], -item.xy[0])):
            anchor = ax.transData.transform(text.xy)
            row = min(range(len(rows)), key=lambda i: abs(rows[i] - anchor[1]))
            bottom = (rows[row - 1] + rows[row]) / 2 if row else axes_box.y0
            top = (rows[row] + rows[row + 1]) / 2 if row + 1 < len(rows) else axes_box.y1
            band = Bbox.from_extents(axes_box.x0 + padding, max(bottom, axes_box.y0 + padding),
                                     axes_box.x1 - padding, min(top, axes_box.y1 - padding))
            forms = [(text.get_text(), text.get_ha(), 8)]
            candidates = []
            originals = []
            for form_index, (label, alignment, offset) in enumerate(forms):
                text.set_text(label)
                text.set_ha(alignment)
                text.set_position((offset, 0))
                original = Text.get_window_extent(text, renderer).frozen()
                originals.append(original)
                xs = [0.0, band.x0 - original.x0, band.x1 - original.x1]
                xs.append(anchor[0] - 8 * unit - original.x1)
                xs += [x * 4 * unit for x in range(
                    int((band.x0 - original.x0) / (4 * unit)),
                    int((band.x1 - original.x1) / (4 * unit)) + 1,
                )]
                center_y = (original.y0 + original.y1) / 2
                low, high = band.y0 - center_y, band.y1 - center_y
                low, high = max(low, -30 * unit), min(high, 30 * unit)
                ys = [0.0, low, high]
                ys += [y * 2 * unit for y in range(int(low / (2 * unit)), int(high / (2 * unit)) + 1)]
                candidates.extend((dx, dy, form_index) for dx in set(xs) for dy in set(ys))
            candidates.sort(key=lambda value: (
                abs(value[0]) + 2 * abs(value[1]) + value[2] * 4 * unit,
                abs(value[1]), value[1] < 0, value[0] < 0, value[2], value[0], value[1],
            ))
            for dx, dy, form_index in candidates:
                original = originals[form_index]
                box = original.translated(dx, dy)
                if not (band.x0 <= box.x0 and box.x1 <= band.x1
                        and band.y0 <= (box.y0 + box.y1) / 2 <= band.y1
                        and axes_box.y0 + padding <= box.y0
                        and box.y1 <= axes_box.y1 - padding):
                    continue
                padded = box.padded(padding)
                obstacles = [other for other in markers + decorations
                             if other.overlaps(band.padded(original.height / 2))]
                if (any(box.padded(0.4 * unit).overlaps(other) for other in obstacles)
                        or any(padded.overlaps(other) for other in placed)):
                    continue
                moved = abs(dx) > 0.01 or abs(dy) > 0.01
                line = _leader_segment(anchor, box) if moved else None
                if any(previous.intersects_bbox(padded, filled=False) for previous in leaders):
                    continue
                if line is not None and (
                    any(line.intersects_bbox(other, filled=False) for other in placed + decorations)
                    or any(line.intersects_bbox(other, filled=False) for other in markers
                           if not other.contains(*anchor))
                    or any(line.intersects_path(previous, filled=False) for previous in leaders)
                ):
                    continue
                label, alignment, offset = forms[form_index]
                text.set_text(label)
                text.set_ha(alignment)
                text.set_position((offset + dx / unit, dy / unit))
                text.arrow_patch.set_visible(moved)
                placed.append(padded)
                if line is not None:
                    leaders.append(line)
                break
            else:
                unresolved += 1
                label, alignment, offset = forms[0]
                text.set_text(label)
                text.set_ha(alignment)
                text.set_position((offset, 0))
                placed.append(originals[0].padded(padding))

    fig.canvas.draw()
    for ax in fig.axes:
        inline = [text for text in ax.texts if isinstance(text, Annotation)
                  and text.get_visible() and (
                      hasattr(text, "_priorityx_compact_parts")
                      or text.get_gid() == "priorityx-transition-suffix")]
        if inline:
            unresolved += _compact_collisions(ax, inline, renderer)
    if unresolved or overlapping_destinations:
        warnings.warn(
            f"{unresolved} transition label(s) could not be placed without collisions "
            f"at this figure size; {overlapping_destinations} destination digit pair(s) overlap. "
            "All events and labels were retained. Increase figsize or render separate "
            "entity_filter pages. For coincident compact digits, choose a finer "
            "x_axis_granularity or label_style='quadrant'; review before delivery.",
            TransitionLabelLayoutWarning,
            stacklevel=2,
        )
    return fig


def plot_transition_timeline(
    transitions_df: pd.DataFrame,
    entity_filter: Optional[List[str]] = None,
    highlight_risk_levels: List[str] = ["critical", "high"],
    filter_risk_levels: Optional[List[str]] = None,
    max_entities: Optional[int] = 20,
    figsize: Optional[Tuple[int, int]] = None,
    title: Optional[str] = None,
    x_axis_granularity: Literal[
        "quarterly", "semiannual", "yearly", "monthly"
    ] = "quarterly",
    sort_by_risk_first: bool = True,
    entity_name: str = "Entity",
    show_all_periods: bool = False,
    # simplified path API (preferred)
    plot_path: Union[str, Path, None] = None,
    csv_path: Union[str, Path, None] = None,
    # deprecated: use plot_path/csv_path instead
    save_plot: bool = False,
    save_csv: bool = False,
    plot_dir: str = "results/plot",
    csv_dir: str = "results/csv",
    plot_filename: Optional[str] = None,
    csv_filename: Optional[str] = None,
    temporal_granularity: str = "quarterly",
    movement_df: Optional[pd.DataFrame] = None,
    close_fig: bool = False,
    label_style: Literal["compact", "quadrant"] = "compact",
    language: str = "en",
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
        figsize: Figure size (width, height) in inches. Defaults to (21, 12)
                 for compact labels and (16, 12) for quadrant labels.
        title: Optional custom title
        x_axis_granularity: Time grouping ('quarterly', 'semiannual', 'yearly')
        sort_by_risk_first: Sort by risk level first (True) or count first (False)
        entity_name: Name for y-axis label
        show_all_periods: Include starting period even if no transitions
        plot_path: Path to save plot (accepts Path or str). If provided, saves plot.
        csv_path: Path to save CSV (accepts Path or str). If provided, saves CSV.
        save_plot: [DEPRECATED] Use plot_path instead. Save plot to file.
        save_csv: [DEPRECATED] Use csv_path instead. Save data to CSV.
        plot_dir: [DEPRECATED] Use plot_path instead. Output directory for plot files.
        csv_dir: [DEPRECATED] Use csv_path instead. Output directory for CSV files.
        temporal_granularity: Time granularity for file naming
        movement_df: Optional movement DataFrame for priority calculation
        close_fig: Close the figure before returning (set True if you see duplicate inline renders)
        label_style: "compact" (default) puts the destination digit in its event
                     marker, e.g. 3→②; "quadrant" retains Q3→Q2 notation.
        language: Display language (``"en"`` by default or ``"id"`` for Indonesian).

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
    language = validate_language(language)
    if label_style not in ("compact", "quadrant"):
        raise ValueError("label_style must be 'compact' or 'quadrant'")
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
    if figsize is None:
        figsize = (21, 12) if label_style == "compact" else (16, 12)
    fig, ax = plt.subplots(figsize=figsize)

    # plot transitions
    priorities_present = set()
    key_examples = []
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

        # add transition label with spike indicator
        from_quad = str(transition["from_quadrant"])
        to_quad = str(transition["to_quadrant"])
        label = f"{from_quad}→{to_quad}"
        spike_suffix = ""

        # avoid duplicating spike markers when to_quadrant already
        # contains *X / *Y / *XY
        has_inline_spike = "*" in to_quad

        if spike_axis and not has_inline_spike:
            # add superscript indicator
            if spike_axis == "Y":
                spike_suffix = "*$^Y$"
            elif spike_axis == "X":
                spike_suffix = "*$^X$"
            elif spike_axis == "XY":
                spike_suffix = "*$^{XY}$"
        label += spike_suffix

        compact = label_style == "compact" and all(
            quadrant.split("*", 1)[0] in ("Q1", "Q2", "Q3", "Q4")
            for quadrant in (from_quad, to_quad)
        )
        if label_style == "compact" and not compact:
            warnings.warn(
                "Unrecognized quadrant code; retaining the complete transition "
                "label for this event in compact mode.", UserWarning, stacklevel=2,
            )
        ax.scatter(x_pos, y_pos, s=196 if compact else 100, c=color, alpha=0.8, zorder=2)
        if compact:
            source, suffix = from_quad[1:], to_quad[2:] + spike_suffix
            suffix = {"*X": "*$^X$", "*Y": "*$^Y$", "*XY": "*$^{XY}$"}.get(suffix, suffix)
            label = f"{source}→"
            ax.text(x_pos, y_pos, to_quad[1], fontsize=12, ha="center", va="center",
                    color="black", zorder=4, gid="priorityx-transition-destination")

        annotation = ax.annotate(
            label,
            (x_pos, y_pos),
            xytext=(-9 if compact else 8, 0),
            textcoords="offset points",
            fontsize=12,
            color="black",
            va="center",
            ha="right" if compact else "left",
            alpha=0.8,
            gid="priorityx-transition-label",
            arrowprops={"arrowstyle": "-", "color": "#777777", "lw": 0.6,
                        "shrinkA": 2, "shrinkB": 8 if compact else 6},
        )
        if compact:
            annotation._priorityx_compact_parts = (source, suffix)
            annotation._priorityx_suffix = ax.annotate(
                suffix, (x_pos, y_pos), xytext=(9, 0), textcoords="offset points",
                fontsize=12, color="black", va="center", ha="left",
                visible=bool(suffix), gid="priorityx-transition-suffix",
            )
            key_examples.append((source, to_quad[1], suffix, color))
        annotation.arrow_patch.set_visible(False)

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
        (1, "#d62728", translate(language, "class_crisis")),
        (2, "#ff7f0e", translate(language, "class_investigate")),
        (3, "#ffdd57", translate(language, "class_monitor")),
        (4, "#2ca02c", translate(language, "class_low")),
    ]

    legend_elements = []
    for priority, color, label in priority_defs:
        if priority in priorities_present:
            legend_elements.append(
                plt.scatter([], [], s=196 if label_style == "compact" else 100,
                            c=color, alpha=0.8, label=label)
            )

    if legend_elements:
        legend_fontsize = 15
        ax.legend(
            handles=legend_elements,
            loc="center left",
            bbox_to_anchor=(1.02, 0.5),
            title=translate(language, "priority"),
            fontsize=legend_fontsize,
            title_fontsize=legend_fontsize,
            frameon=False,
        )

        if key_examples:
            # Prefer a complete spike example; ties retain input order.
            example = max(key_examples, key=lambda item: ("XY" in item[2], item[0] == "1", bool(item[2])))
            _make_transition_key(ax, example, language)
        else:
            ax.text(1.02, 0.25,
                    f"*$^Y$ = {translate(language, 'y_spike')}\n"
                    f"*$^X$ = {translate(language, 'x_spike')}",
                    transform=ax.transAxes, fontsize=12, ha="left", va="top")

    # set labels
    xlabel_map = {
        "quarterly": translate(language, "quarter"),
        "semiannual": translate(language, "semester"),
        "yearly": translate(language, "year"),
        "monthly": translate(language, "month"),
    }
    axis_fontsize = 15
    ax.set_xlabel(xlabel_map.get(x_axis_granularity, translate(language, "period")), fontsize=axis_fontsize)
    
    # The caller owns the entity label. Do not infer a domain from the name.
    ylabel = entity_name
    ax.set_ylabel(ylabel, fontsize=axis_fontsize)
    ax.set_yticklabels(entities, fontsize=tick_fontsize)

    # Only set title if not empty
    if title is None:
        title = f"{ylabel} {translate(language, 'transition_timeline_title')}"
    if title:  # Skip if empty string
        ax.set_title(title, fontsize=17, fontweight="bold", pad=20)

    ax.tick_params(axis="both", which="major", labelsize=tick_fontsize)
    plt.tight_layout()
    layout_transition_labels(fig, language)

    # determine actual save paths
    actual_plot_path: Optional[Path] = None
    actual_csv_path: Optional[Path] = None

    # new API takes precedence
    if plot_path is not None:
        actual_plot_path = Path(plot_path)
    elif save_plot:
        warnings.warn(
            "save_plot/plot_dir/plot_filename are deprecated. Use plot_path instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        from datetime import datetime

        if plot_filename:
            actual_plot_path = Path(plot_dir) / plot_filename
        else:
            timestamp = datetime.now().strftime("%Y%m%d")
            granularity_suffix = {
                "quarterly": "Q",
                "yearly": "Y",
                "semiannual": "S",
                "monthly": "M",
            }.get(temporal_granularity, "Q")
            entity_slug = entity_name.lower().replace(" ", "_")
            actual_plot_path = Path(plot_dir) / f"transition_timeline-{entity_slug}-{granularity_suffix}-{timestamp}.png"

    if csv_path is not None:
        actual_csv_path = Path(csv_path)
    elif save_csv:
        warnings.warn(
            "save_csv/csv_dir/csv_filename are deprecated. Use csv_path instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        from datetime import datetime

        if csv_filename:
            actual_csv_path = Path(csv_dir) / csv_filename
        else:
            timestamp = datetime.now().strftime("%Y%m%d")
            granularity_suffix = {
                "quarterly": "Q",
                "yearly": "Y",
                "semiannual": "S",
                "monthly": "M",
            }.get(temporal_granularity, "Q")
            entity_slug = entity_name.lower().replace(" ", "_")
            actual_csv_path = Path(csv_dir) / f"transitions-{entity_slug}-{granularity_suffix}-{timestamp}.csv"

    # save plot if path determined
    if actual_plot_path:
        actual_plot_path.parent.mkdir(parents=True, exist_ok=True)
        # Measure at the renderer's export DPI before writing the PNG.
        original_dpi = fig.dpi
        try:
            fig.set_dpi(300)
            layout_transition_labels(fig)
            fig.savefig(actual_plot_path, dpi=300, bbox_inches="tight", format="png")
        finally:
            fig.set_dpi(original_dpi)
            layout_transition_labels(fig)
        print(f"Transition plot saved: {actual_plot_path}")

    # save CSV if path determined
    if actual_csv_path:
        actual_csv_path.parent.mkdir(parents=True, exist_ok=True)
        df_to_save = df
        # for monthly outputs, rename column
        if temporal_granularity == "monthly" and "transition_quarter" in df.columns:
            df_to_save = df.copy().rename(
                columns={"transition_quarter": "transition_month"}
            )
        df_to_save.to_csv(actual_csv_path, index=False)
        print(f"Transitions CSV saved: {actual_csv_path}")

    if close_fig:
        plt.close(fig)

    return fig
