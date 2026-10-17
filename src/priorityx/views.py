"""Shared saved-result chart semantics and versioned, portable view settings.

No fitting or source-column mapping occurs here. Display windows never replace
full saved histories used by the existing event classifier.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
import hashlib
import json
import math
from typing import Any

import pandas as pd

from .results import ResultBundle, ResultDataset, ResultValidationError, _period_column, _PERIOD
from .tracking.transitions import classify_priority

VIEW_SCHEMA_VERSION = 1
VIEW_LIMITS = {
    "panel_height": {"min": 320, "max": 1000, "integer": True},
    "min_panel_width": {"min": 320, "max": 1200, "integer": True},
    "timeline_scale": {"min": .5, "max": 3, "integer": False},
    "dpi": {"min": 72, "max": 300, "integer": True},
    "static_width": {"min": 6, "max": 40, "integer": False, "nullable": True},
    "static_height": {"min": 4, "max": 30, "integer": False, "nullable": True},
}


def dataset_key(entity_type: str, cadence: str) -> str:
    return json.dumps([entity_type, cadence], ensure_ascii=False, separators=(",", ":"))


def bundle_identity(bundle: ResultBundle) -> str:
    encoded = json.dumps(bundle.to_dict(), sort_keys=True, ensure_ascii=False,
                         separators=(",", ":"), allow_nan=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def periods_ending(as_of: str, cadence: str, count: int) -> list[str]:
    freq = "M" if cadence == "monthly" else "Q"
    end = pd.Period(as_of, freq=freq)
    return [str(p) if cadence == "monthly" else f"{p.year}-Q{p.quarter}"
            for p in pd.period_range(end=end, periods=count, freq=freq)]


def timeline_periods(dataset: dict[str, Any]) -> list[str]:
    """Snapshot-year periods including blank periods, independent of wall clock."""
    as_of, cadence = dataset["asOf"], dataset["cadence"]
    count = int(as_of[-2:]) if cadence == "monthly" else int(as_of[-1])
    return periods_ending(as_of, cadence, count)


def _selection(dataset: ResultDataset, name: str, available: list[str]) -> list[str]:
    value = dataset.selections.get(name)
    if value is None:
        return available
    if (not isinstance(value, list) or any(not isinstance(x, str) for x in value)
            or len(value) != len(set(value))):
        raise ResultValidationError(f"selections.{name} must be unique string identifiers")
    if set(value) - set(available):
        raise ResultValidationError(f"selections.{name} contains unavailable identifiers")
    return list(value)


def _events(dataset: ResultDataset) -> list[dict[str, Any]]:
    if dataset.transitions is None:
        return []
    tp = _period_column(dataset.transitions, dataset.cadence, "transitions")
    movement = dataset.movement
    mp = _period_column(movement, dataset.cadence, "movement") if movement is not None else None
    output = []
    for row in dataset.transitions.to_dict("records"):
        priority, spike = 2, None
        if movement is not None:
            current = movement[(movement.entity == row["entity"]) & (movement[mp] == row[tp])]
            previous = movement[(movement.entity == row["entity"]) & (movement[mp] < row[tp])]
            # Match plot_transition_timeline: use the last saved previous row,
            # without sorting or filtering full history before classification.
            if not current.empty and not previous.empty and "cumulative_count" in movement:
                now, prev = current.iloc[0], previous.iloc[-1]
                delta = now.cumulative_count - prev.cumulative_count
                percent = delta / prev.cumulative_count * 100 if prev.cumulative_count > 0 else 0
                priority, _, spike = classify_priority(
                    row["from_quadrant"], row["to_quadrant"], now.period_x, now.period_y,
                    now.period_x - prev.period_x, now.period_y - prev.period_y,
                    int(delta), percent,
                )
        destination = row["to_quadrant"]
        inline = destination.split("*", 1)
        suffix = "*" + inline[1] if len(inline) > 1 else ("*" + spike if spike else "")
        output.append({"entity": row["entity"], "period": row[tp],
                       "source": row["from_quadrant"][1:], "destination": destination[1],
                       "suffix": suffix, "class": priority})
    return output


def _trajectory_selection(dataset: ResultDataset, paths: dict, periods: list[str]) -> tuple[list[str], dict]:
    if "trajectory_entities" in dataset.selections:
        return _selection(dataset, "trajectory_entities", list(paths)), {"mode": "saved", "scores": {}}
    window = set(periods)
    scores = {}
    for entity, points in paths.items():
        if not any(p["period"] in window for p in points):
            continue
        # Use full saved history for the change into the first visible period.
        # Optional saved delta columns are not required by the bundle contract.
        changes = [abs(current["y"] - previous["y"])
                   for previous, current in zip(points, points[1:]) if current["period"] in window]
        try:
            score = math.fsum(changes)
        except OverflowError as exc:
            raise ResultValidationError("Trajectory movement exceeds the supported numeric range") from exc
        if not math.isfinite(score):
            raise ResultValidationError("Trajectory movement exceeds the supported numeric range")
        scores[entity] = score
    selected = sorted(scores, key=lambda entity: (-scores[entity], entity))[:3]
    return selected, {"mode": "trend_change", "scores": {entity: scores[entity] for entity in selected}}


def prepare_bundle(bundle: ResultBundle) -> dict[str, Any]:
    """Validate and prepare both renderers without changing analytical values."""
    bundle = ResultBundle.from_dict(bundle.to_dict())
    datasets = []
    for d in bundle.datasets:
        matrix = [] if d.matrix is None else [
            {"entity": r["entity"], "x": r["x_score"], "y": r["y_score"],
             "count": r["count"], "quadrant": r["quadrant"]}
            for r in d.matrix.to_dict("records")]
        paths = {}
        if d.movement is not None:
            mp = _period_column(d.movement, d.cadence, "movement")
            for entity, group in d.movement.groupby("entity", sort=False):
                paths[entity] = [{"period": r[mp], "x": r["period_x"],
                                  "y": r["period_y"], "quadrant": r["global_quadrant"]}
                                 for r in group.sort_values(mp, kind="stable").to_dict("records")]
        events = _events(d)
        risks = d.selections.get("timeline_risk_levels")
        if risks is not None:
            allowed_risks = {"critical", "high", "medium", "low", "stable"}
            if (not isinstance(risks, list) or any(not isinstance(r, str) or r not in allowed_risks for r in risks)
                    or len(risks) != len(set(risks))):
                raise ResultValidationError("selections.timeline_risk_levels must be unique supported risk levels")
            events = [event for event, row in zip(events, d.transitions.to_dict("records") if d.transitions is not None else [])
                      if row["risk_level"] in risks]
        cutoff = d.selections.get("timeline_start_period")
        if cutoff is not None:
            if (not isinstance(cutoff, str) or not _PERIOD[d.cadence].fullmatch(cutoff)
                    or cutoff > d.as_of):
                raise ResultValidationError("selections.timeline_start_period must be a canonical period no later than as_of")
            events = [e for e in events if e["period"] >= cutoff]
        rows = _selection(d, "timeline_entities", list(dict.fromkeys(e["entity"] for e in events)))
        events = [e for e in events if e["entity"] in rows]
        count = d.selections.get("trajectory_periods", 12 if d.cadence == "monthly" else 8)
        if type(count) is not int or not 1 <= count <= 120:
            raise ResultValidationError("selections.trajectory_periods must be an integer from 1 to 120")
        path_periods = periods_ending(d.as_of, d.cadence, count)
        selected_paths, selection = _trajectory_selection(d, paths, path_periods)
        item = {"key": dataset_key(d.entity_type, d.cadence), "entity_type": d.entity_type,
                "typeLabel": d.type_label if d.type_label is not None else d.entity_type,
                "cadence": d.cadence, "source_id": d.source_id,
                "coverage_start": d.coverage_start, "asOf": d.as_of,
                "matrix": matrix, "paths": paths, "defaultPaths": selected_paths,
                "events": events, "rows": rows, "periods": [],
                "pathWindow": count, "pathPeriods": path_periods,
                "trajectorySelection": selection,
                "availability": {"matrix": d.matrix is not None,
                                 "timeline": d.transitions is not None,
                                 "paths": d.movement is not None},
                "warnings": []}
        item["periods"] = timeline_periods(item)
        if d.transitions is not None and (d.movement is None or "cumulative_count" not in d.movement):
            item["warnings"].append("Saved movement counts are unavailable; event classes use the default Investigate class.")
        datasets.append(item)
    return {"schema_version": 1, "bundle_id": bundle_identity(bundle), "settings_schema": {name: limit.copy() for name, limit in VIEW_LIMITS.items()},
            "producer_version": bundle.producer_version, "datasets": datasets}


def _finite_json(value: Any, depth: int = 0) -> None:
    if depth > 12:
        raise ResultValidationError("view state nesting exceeds 12 levels")
    if value is None or isinstance(value, (str, bool)):
        return
    if isinstance(value, (int, float)) and math.isfinite(value):
        return
    if isinstance(value, list) and len(value) <= 10000:
        for x in value:
            _finite_json(x, depth + 1)
        return
    if isinstance(value, dict) and len(value) <= 10000 and all(isinstance(k, str) for k in value):
        for x in value.values():
            _finite_json(x, depth + 1)
        return
    raise ResultValidationError("view state must contain bounded finite JSON values")


def _validate_interaction(value: Any) -> None:
    """Validate the browser's persisted ranges, positions and disclosures."""
    allowed = {"ranges", "timeline", "row_left", "focus", "disclosures", "tables", "data_tab", "paths_scope"}
    if not isinstance(value, dict) or set(value) - allowed:
        raise ResultValidationError("invalid dataset interaction fields")

    def position(x):
        if type(x) not in (int, float) or not math.isfinite(x) or not 0 <= x <= 100000000:
            raise ResultValidationError("view positions must be finite non-negative numbers")

    ranges = value.get("ranges", {})
    if not isinstance(ranges, dict) or set(ranges) - {"matrix", "paths"}:
        raise ResultValidationError("invalid chart-range family")
    for bounds in ranges.values():
        if not isinstance(bounds, dict) or set(bounds) != {"x", "y"}:
            raise ResultValidationError("chart ranges require x and y bounds")
        for axis in bounds.values():
            if (not isinstance(axis, list) or len(axis) != 2
                    or any(type(x) not in (int, float) or not math.isfinite(x) for x in axis)
                    or axis[0] >= axis[1]):
                raise ResultValidationError("chart bounds must be increasing finite pairs")
    timeline = value.get("timeline", {})
    if not isinstance(timeline, dict) or set(timeline) - {"left", "top", "row", "row_offset"}:
        raise ResultValidationError("invalid timeline position fields")
    for key, x in timeline.items():
        if key == "row":
            if not isinstance(x, str):
                raise ResultValidationError("timeline row anchor must be a string")
        else:
            position(x)
    position(value.get("row_left", 0))
    if value.get("focus", "matrix") not in {"matrix", "timeline", "paths"}:
        raise ResultValidationError("invalid focused chart")
    if value.get("data_tab", "matrix") not in ("matrix", "timeline", "paths"):
        raise ResultValidationError("invalid data tab")
    if value.get("paths_scope", "shown") not in ("shown", "all"):
        raise ResultValidationError("invalid trajectory table scope")
    disclosures = value.get("disclosures", {})
    # Earlier settings used independent table folds. The browser maps them to
    # the shared data panel; transient settings/import dialogs are not reopened.
    names = {"data-panel", "details", "matrix-data", "timeline-data", "paths-data", "layout-settings", "import-panel"}
    if (not isinstance(disclosures, dict) or set(disclosures) - names
            or any(type(x) is not bool for x in disclosures.values())):
        raise ResultValidationError("invalid disclosure state")
    tables = value.get("tables", {})
    if not isinstance(tables, dict) or set(tables) - {"matrix", "timeline", "paths"}:
        raise ResultValidationError("invalid table position fields")
    for x in tables.values():
        position(x)


@dataclass
class ViewSettings:
    """Source-bound display settings; browser interaction state belongs in views."""
    bundle_id: str
    entity_type: str = ""
    cadence: str = "quarterly"
    member: str = ""
    panel_height: int = 422
    min_panel_width: int = 380
    timeline_scale: float = 1
    layout_mode: str = "auto"
    static_width: float | None = None
    static_height: float | None = None
    dpi: int = 150
    views: dict[str, Any] = field(default_factory=dict)
    schema_version: int = VIEW_SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, value: dict[str, Any], prepared: dict[str, Any]) -> "ViewSettings":
        if not isinstance(value, dict) or set(value) - set(cls.__dataclass_fields__):
            raise ResultValidationError("unknown or invalid view-settings fields")
        if value.get("bundle_id") != prepared["bundle_id"]:
            raise ResultValidationError("settings belong to a different saved-result bundle")
        settings = cls(**value)
        if type(settings.schema_version) is not int or settings.schema_version != 1:
            raise ResultValidationError("unsupported view-settings schema_version")
        for name, limit in VIEW_LIMITS.items():
            low, high, integer = limit["min"], limit["max"], limit["integer"]
            x = getattr(settings, name)
            if x is None and limit.get("nullable"):
                continue
            if (type(x) not in (int, float) or not math.isfinite(x) or not low <= x <= high
                    or (integer and x % 1 != 0)):
                raise ResultValidationError(f"{name} must be {'an integer' if integer else 'a number'} from {low} to {high}")
            if integer:
                setattr(settings, name, int(x))
        if settings.layout_mode not in ("auto", "manual"):
            raise ResultValidationError("layout_mode must be auto or manual")
        if settings.layout_mode == "manual" and (settings.static_width is None or settings.static_height is None):
            raise ResultValidationError("manual print size requires both width and height")
        if not isinstance(settings.entity_type, str) or not isinstance(settings.member, str):
            raise ResultValidationError("entity_type and member must be strings")
        if settings.cadence not in ("monthly", "quarterly"):
            raise ResultValidationError("cadence must be monthly or quarterly")
        if not isinstance(settings.views, dict):
            raise ResultValidationError("views must be an object keyed by dataset key")
        _finite_json(settings.views)
        if len(json.dumps(settings.views, ensure_ascii=False).encode("utf-8")) > 500000:
            raise ResultValidationError("saved interaction state exceeds 500 KB")
        datasets = prepared["datasets"]
        keys = {d["key"] for d in datasets}
        if set(settings.views) - keys:
            raise ResultValidationError("view state contains an unknown dataset")
        for value in settings.views.values():
            _validate_interaction(value)
        if datasets:
            matches = [d for d in datasets if d["entity_type"] == settings.entity_type and d["cadence"] == settings.cadence]
            if not matches:
                raise ResultValidationError("settings type/cadence is unavailable in this bundle")
            members = set(matches[0]["paths"]) | {r["entity"] for r in matches[0]["matrix"]} | set(matches[0]["rows"])
            if settings.member and settings.member not in members:
                raise ResultValidationError("selected member is unavailable in this dataset")
        elif settings.entity_type or settings.member:
            raise ResultValidationError("empty bundles cannot select a type or member")
        return settings


def resolve_settings(settings: ViewSettings | dict[str, Any] | None,
                     prepared: dict[str, Any]) -> ViewSettings:
    if settings is None:
        datasets = prepared["datasets"]
        opening = next((d for d in datasets if d["cadence"] == "quarterly"), datasets[0] if datasets else None)
        settings = ViewSettings(prepared["bundle_id"],
                                entity_type=opening["entity_type"] if opening else "",
                                cadence=opening["cadence"] if opening else "quarterly")
    return ViewSettings.from_dict(settings.to_dict() if isinstance(settings, ViewSettings) else settings, prepared)


@dataclass
class LayoutReport:
    """Measured renderer outcome; unresolved labels are retained and reported."""
    bundle_id: str
    dataset_key: str
    renderer: str
    renderer_version: str
    dimensions: dict[str, Any]
    resolved_settings: dict[str, Any]
    warnings: list[str] = field(default_factory=list)
    unresolved: int = 0
    schema_version: int = 1

    @property
    def status(self) -> str:
        return "unresolved" if self.unresolved else "ready"

    def to_dict(self) -> dict[str, Any]:
        return {**asdict(self), "status": self.status}
