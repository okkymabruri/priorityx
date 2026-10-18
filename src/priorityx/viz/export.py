"""Opt-in static rendering from the same saved chart payload as the browser.

Existing plotting APIs and their defaults are unaffected. The bounded search
retains all marks and labels, and reports constraints that it cannot resolve.
"""
from __future__ import annotations

import textwrap
from typing import Any

import matplotlib
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure
from matplotlib.text import Text
from matplotlib.transforms import Bbox

from priorityx.results import ResultValidationError
from priorityx.views import LayoutReport, ViewSettings

_COLORS = {1: "#d62728", 2: "#ff7f0e", 3: "#ffdd57", 4: "#2ca02c"}
_QUADRANT_COLORS = {"Q1": "#d62728", "Q2": "#ff7f0e", "Q3": "#2ca02c", "Q4": "#1f77b4"}


def _line_paths(ax):
    return [line.get_transform().transform_path(line.get_path())
            for line in ax.lines if line.get_visible() and line.get_linestyle() != "None"]


def _issues(fig, ax, labels, points):
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    bounds = ax.get_window_extent(renderer)
    boxes = [Text.get_window_extent(t, renderer).expanded(1.02, 1.08) for t in labels]
    paths = _line_paths(ax)
    unresolved = 0
    for i, box in enumerate(boxes):
        clipped = box.x0 < bounds.x0 or box.x1 > bounds.x1 or box.y0 < bounds.y0 or box.y1 > bounds.y1
        overlaps = any(box.overlaps(b) for b in boxes[:i])
        marker_overlap = any(box.overlaps(b) for b in points)
        line_overlap = any(path.intersects_bbox(box, filled=False) for path in paths)
        if clipped or overlaps or marker_overlap or line_overlap:
            unresolved += 1
    figure_bounds = fig.bbox
    tick_groups = []
    for locations, ticks, limits in ((ax.get_xticks(), ax.get_xticklabels(), ax.get_xlim()),
                                      (ax.get_yticks(), ax.get_yticklabels(), ax.get_ylim())):
        low, high = sorted(limits)
        tick_groups.append([label for location, label in zip(locations, ticks)
                            if low <= location <= high])
    for ticks in tick_groups:
        measured = [t.get_window_extent(renderer).expanded(1.02, 1.10)
                    for t in ticks if t.get_visible() and t.get_text()]
        for i, box in enumerate(measured):
            if (box.x0 < figure_bounds.x0 or box.x1 > figure_bounds.x1
                    or box.y0 < figure_bounds.y0 or box.y1 > figure_bounds.y1
                    or any(box.overlaps(b) for b in measured[:i])):
                unresolved += 1
    furniture = []
    for artist in [ax.title, *fig.texts, *([ax.get_legend()] if ax.get_legend() else [])]:
        box = artist.get_window_extent(renderer)
        if (box.x0 < figure_bounds.x0 or box.x1 > figure_bounds.x1
                or box.y0 < figure_bounds.y0 or box.y1 > figure_bounds.y1):
            unresolved += 1
        if any(box.overlaps(other) for other in furniture):
            unresolved += 1
        furniture.append(box)
    return unresolved


def _point_labels(fig, ax, labels):
    """Choose measured fixed-offset candidates; never change saved coordinates."""
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    bounds = ax.get_window_extent(renderer)
    radius = fig.dpi / 72 * 5
    points = [Bbox.from_bounds(x - radius, y - radius, radius * 2, radius * 2)
              for collection in ax.collections for point in collection.get_offsets()
              for x, y in [ax.transData.transform(point)]]
    paths = _line_paths(ax)
    accepted = []
    for i, label in enumerate(labels):
        candidates = [(offset, ha, va) for radius in (9, 18, 36, 64)
                      for offset, ha, va in (((radius, radius), "left", "bottom"),
                                             ((-radius, radius), "right", "bottom"),
                                             ((radius, -radius), "left", "top"),
                                             ((-radius, -radius), "right", "top"),
                                             ((0, radius), "center", "bottom"),
                                             ((0, -radius), "center", "top"))]
        for offset, ha, va in candidates:
            label.set_position(offset)
            label.set_ha(ha)
            label.set_va(va)
            fig.canvas.draw()
            box = Text.get_window_extent(label, renderer).expanded(1.02, 1.08)
            if (box.x0 >= bounds.x0 and box.x1 <= bounds.x1 and box.y0 >= bounds.y0
                    and box.y1 <= bounds.y1 and not any(box.overlaps(b) for b in accepted + points)
                    and not any(path.intersects_bbox(box, filled=False) for path in paths)):
                break
        accepted.append(Text.get_window_extent(label, renderer).expanded(1.02, 1.08))
    return _issues(fig, ax, labels, points)


def _build(dataset, settings, family, size):
    fig = Figure(figsize=size, dpi=settings.dpi)
    FigureCanvasAgg(fig)
    ax = fig.subplots()
    fig.subplots_adjust(left=.24 if family == "timeline" else .11, right=.95,
                        bottom=.95 / size[1] if family == "timeline" else .16,
                        top=1 - .8 / size[1] if family == "timeline" else .86)
    ax.tick_params(labelsize=12)
    labels = []
    member = settings.member
    if family == "matrix":
        rows = dataset["matrix"]
        for row in rows:
            ax.scatter(row["x"], row["y"], s=65, color=_QUADRANT_COLORS[row["quadrant"]],
                       alpha=.9 if not member or member == row["entity"] else .25, zorder=3)
            if member != row["entity"]:
                continue
            label = ax.annotate(textwrap.fill(row["entity"], 25), (row["x"], row["y"]),
                                xytext=(9, 9), textcoords="offset points", fontsize=12,
                                fontweight="bold" if row["entity"] == member else "normal")
            labels.append(label)
        ax.set_xlabel("Level", fontsize=12)
        ax.set_ylabel("Trend", fontsize=12)
    elif family == "paths":
        names = [member] if member else dataset["defaultPaths"]
        for name in names:
            path = [p for p in dataset["paths"].get(name, []) if p["period"] in dataset["pathPeriods"]]
            if not path:
                continue
            ax.plot([p["x"] for p in path], [p["y"] for p in path], "-",
                            color=_QUADRANT_COLORS[path[0]["quadrant"]])
            ax.scatter([p["x"] for p in path], [p["y"] for p in path], s=35,
                       c=[_QUADRANT_COLORS[p["quadrant"]] for p in path], zorder=3)
            labels.append(ax.annotate(textwrap.fill(name, 28) + "\n" + path[-1]["period"],
                                      (path[-1]["x"], path[-1]["y"]),
                                      xytext=(9, 9), textcoords="offset points", fontsize=12,
                                      color="#26382c", arrowprops={"arrowstyle": "-", "color": "#718176", "lw": .7}))
        ax.set_xlabel("Level", fontsize=12)
        ax.set_ylabel("Trend", fontsize=12)
    else:
        periods = dataset["periods"]
        events = [e for e in dataset["events"] if e["period"] in periods and e["entity"] in dataset["rows"]]
        names = dataset["rows"]
        ax.set_xticks(range(len(periods)), periods)
        ax.xaxis.tick_top()
        ax.tick_params(axis="x", pad=10)
        wrap_at = max(20, int((size[0] * 72 * .24 - 24) / 6))
        ax.set_yticks(range(len(names)), [textwrap.fill(n, wrap_at) for n in names])
        ax.set_ylim(len(names) - .5 if names else .5, -.5)
        ax.set_xlim(-.6, len(periods) - .4)
        for event in events:
            if event["entity"] not in names:
                continue
            x, y = periods.index(event["period"]), names.index(event["entity"])
            ax.scatter(x, y, s=196, color=_COLORS[event["class"]],
                       alpha=.9 if not member or member == event["entity"] else .25, zorder=3)
            ax.text(x, y, event["destination"], ha="center", va="center", fontsize=12,
                    color="white" if event["class"] == 1 else "black", zorder=4)
            before = ax.annotate(event["source"] + "→", (x, y), xytext=(-9, 0),
                                 textcoords="offset points", fontsize=12, ha="right", va="center")
            after = ax.annotate(event["suffix"], (x, y), xytext=(9, 0),
                                textcoords="offset points", fontsize=12, ha="left", va="center")
            labels.extend([before, after])
        ax.grid(axis="x", alpha=.2)
        hidden = len(dataset["events"]) - len(events)
        fig.text(.24, .35 / size[1], f"YTD through {dataset['asOf']} · {hidden} earlier events outside YTD", fontsize=12)
        fig.text(.24, .12 / size[1], "*X / *Y / *XY: score-axis spike", fontsize=12)
    ax.set_title({"matrix": "Quadrant matrix", "timeline": "Transition timeline", "paths": "Trajectories"}[family],
                 fontsize=14, pad=38 if family == "timeline" else 16)
    if family != "timeline":
        ax.axhline(0, color="#aaaaaa", linewidth=.7)
        ax.axvline(0, color="#aaaaaa", linewidth=.7)
        ax.margins(.25)
        from matplotlib.lines import Line2D
        ax.legend(handles=[Line2D([], [], color=color, marker="o", linestyle="", label=q)
                           for q, color in _QUADRANT_COLORS.items()], ncol=4, fontsize=12,
                  frameon=False, loc="upper left", bbox_to_anchor=(0, -.11))
        unresolved = _point_labels(fig, ax, labels)
    else:
        from matplotlib.lines import Line2D
        ax.legend(handles=[Line2D([], [], color=_COLORS[i], marker="o", linestyle="", label=name)
                           for i, name in enumerate(["Crisis", "Investigate", "Monitor", "Low"], 1)],
                  ncol=4, fontsize=12, frameon=False, loc="lower left", borderaxespad=0,
                  bbox_transform=fig.transFigure, bbox_to_anchor=(.24, .60 / size[1]))
        unresolved = _issues(fig, ax, labels, [])
    return fig, unresolved


def render_static(dataset: dict[str, Any], settings: ViewSettings, family: str):
    """Return ``(Figure, LayoutReport)`` with bounded deterministic sizing.

    Dimensions supplied by the caller win. An unresolved report is a retained
    chart requiring a wider/taller profile, never permission to drop content.
    """
    if family not in ("matrix", "timeline", "paths"):
        raise ResultValidationError("family must be matrix, timeline or paths")
    if not dataset["availability"][family]:
        raise ResultValidationError(f"{family} saved results are unavailable")
    manual = settings.layout_mode == "manual" or settings.static_width is not None or settings.static_height is not None
    row_count = len(dataset["rows"])
    lines = max((len(textwrap.fill(n, 32).splitlines()) for n in dataset["rows"]), default=1)
    base_height = min(30, max(8, row_count * (lines * 14.4 + 8) / 72 + 1.8)) if family == "timeline" else 9
    sizes = [(14, base_height), (18, min(30, max(10, base_height + 2))),
             (24, min(30, max(12, base_height + 4))), (32, min(30, max(16, base_height + 6)))]
    if manual:
        sizes = [(settings.static_width or 14, settings.static_height or base_height)]
    fig = None
    for size in sizes:
        if size[0] * size[1] * settings.dpi ** 2 > 32000000:
            raise ResultValidationError("Print dimensions exceed 32 million pixels at this DPI; lower DPI or choose smaller dimensions.")
        if fig is not None:
            fig.clear()
        fig, unresolved = _build(dataset, settings, family, size)
        if not unresolved:
            break
    warnings = list(dataset.get("warnings", []))
    if unresolved:
        warnings.append(f"{unresolved} labels remain overlapping or outside the plot; all values and labels are retained. Choose a wider/taller static profile.")
    if settings.member:
        available = ({r["entity"] for r in dataset["matrix"]} if family == "matrix" else
                     set(dataset["paths"]) if family == "paths" else set(dataset["rows"]))
        if settings.member not in available:
            warnings.append(f"Selected member has no saved {family} data.")
    return fig, LayoutReport(settings.bundle_id, dataset["key"], "matplotlib", matplotlib.__version__,
                             {"width_inches": size[0], "height_inches": size[1], "dpi": settings.dpi},
                             settings.to_dict(), warnings, unresolved)
