"""Portable saved-result bundles for the local visualisation workflow.

The module deliberately stores tables as records plus their column list.  This
keeps empty table schemas and string identifiers intact without serialising
Python objects or embedding machine-local paths.
"""

from __future__ import annotations

import hashlib
import csv
import io
import json
import math
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

import pandas as pd

from . import __version__

SCHEMA_VERSION = 1
_PERIOD = {
    "monthly": re.compile(r"^\d{4}-(0[1-9]|1[0-2])$"),
    "quarterly": re.compile(r"^\d{4}-Q[1-4]$"),
}
_QUADRANT = re.compile(r"^Q[1-4](?:\*(?:X|Y|XY))?$")
_RISK = {"critical", "high", "medium", "low", "stable"}
_ROLE_COLUMNS = {
    "matrix": {"entity", "x_score", "y_score", "count", "quadrant"},
    "movement": {
        "entity",
        "period_x",
        "period_y",
        "period_quadrant",
        "global_quadrant",
    },
    "transitions": {"entity", "from_quadrant", "to_quadrant", "risk_level"},
}
_NUMERIC = {
    "matrix": {"x_score", "y_score", "count"},
    "movement": {
        "period_x",
        "period_y",
        "global_x",
        "global_y",
        "count_total",
        "x_delta",
        "y_delta",
        "period_count",
        "cumulative_count",
    },
    "transitions": {"volume_change", "growth_change"},
}
_NULLABLE_NUMERIC = {
    "x_delta",
    "y_delta",
    "period_count",
    "volume_change",
    "growth_change",
}


class ResultValidationError(ValueError):
    """Raised when a saved result cannot satisfy the bundle contract."""


def strict_json_loads(text: str) -> Any:
    """Read portable JSON, rejecting duplicate fields before values are lost."""
    def unique_fields(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ResultValidationError(f"duplicate JSON field: {key}")
            result[key] = value
        return result

    def invalid_constant(value):
        raise ResultValidationError(f"invalid JSON constant: {value}")

    try:
        return json.loads(text, object_pairs_hook=unique_fields,
                          parse_constant=invalid_constant)
    except (json.JSONDecodeError, TypeError) as exc:
        raise ResultValidationError(f"invalid JSON: {exc}") from exc


def _period_column(frame: pd.DataFrame, cadence: str, role: str) -> str | None:
    expected = "month" if cadence == "monthly" else "quarter"
    if role == "transitions":
        expected = "transition_quarter"
    aliases = {expected}
    if role == "movement" and cadence == "monthly":
        # track_movement historically calls its canonical period column quarter,
        # including when its values are monthly.  Preserve that explicit alias.
        aliases.add("quarter")
    if role == "transitions":
        aliases |= {"transition_month"} if cadence == "monthly" else set()
    present = aliases & set(frame.columns)
    if len(present) > 1:
        raise ResultValidationError(
            f"{role} has ambiguous period columns: {sorted(present)}"
        )
    if role == "movement" and cadence == "quarterly" and "month" in frame:
        raise ResultValidationError("quarterly movement cannot have a month column")
    if role == "transitions" and cadence == "quarterly" and "transition_month" in frame:
        raise ResultValidationError(
            "quarterly transitions cannot have a transition_month column"
        )
    return next(iter(present), None)


def _clean_frame(frame: pd.DataFrame, role: str, cadence: str) -> pd.DataFrame:
    if not isinstance(frame, pd.DataFrame):
        raise ResultValidationError(f"{role} must be a pandas DataFrame")
    out = frame.copy()
    if not out.columns.is_unique or any(
        not isinstance(c, str) or not c for c in out.columns
    ):
        raise ResultValidationError(f"{role} must have unique non-empty string columns")
    missing = _ROLE_COLUMNS[role] - set(out.columns)
    if missing:
        raise ResultValidationError(
            f"{role} missing required columns: {sorted(missing)}"
        )
    period = _period_column(out, cadence, role)
    if role in {"movement", "transitions"} and period is None:
        raise ResultValidationError(
            f"{role} requires the explicit {('month' if cadence == 'monthly' else 'quarter')} period column"
        )
    if "entity" in out:
        if (
            out["entity"].isna().any()
            or not out["entity"]
            .map(lambda x: isinstance(x, str) and bool(x.strip()))
            .all()
        ):
            raise ResultValidationError(f"{role}.entity contains an empty identifier")
    if period:
        bad = out[period].isna() | ~out[period].astype(str).map(
            _PERIOD[cadence].fullmatch
        ).astype(bool)
        if bad.any():
            raise ResultValidationError(
                f"{role}.{period} contains invalid {cadence} periods"
            )
        out[period] = out[period].astype(str)
    for col in _NUMERIC[role] & set(out.columns):
        if out[col].map(lambda x: isinstance(x, bool)).any():
            raise ResultValidationError(f"{role}.{col} cannot contain boolean values")
        vals = pd.to_numeric(out[col], errors="coerce")
        nonnull = out[col].notna()
        if col not in _NULLABLE_NUMERIC and not nonnull.all():
            raise ResultValidationError(f"{role}.{col} cannot contain null values")
        if vals[nonnull].isna().any() or not vals[nonnull].map(math.isfinite).all():
            raise ResultValidationError(
                f"{role}.{col} contains non-finite or non-numeric values"
            )
        if (
            col in {"count", "count_total", "period_count", "cumulative_count"}
            and ((vals[nonnull] < 0) | (vals[nonnull] % 1 != 0)).any()
        ):
            raise ResultValidationError(
                f"{role}.{col} must contain non-negative integers"
            )
        out[col] = vals
    if role == "matrix":
        if out["entity"].duplicated().any():
            raise ResultValidationError("matrix.entity values must be unique")
        if (
            ~out["quadrant"].astype(str).map(lambda x: bool(re.fullmatch(r"Q[1-4]", x)))
        ).any():
            raise ResultValidationError("matrix.quadrant contains an unsupported value")
    elif role == "movement":
        if out.duplicated(["entity", period]).any():
            raise ResultValidationError("movement entity/period values must be unique")
        for col in ("period_quadrant", "global_quadrant"):
            if (
                ~out[col].astype(str).map(lambda x: bool(re.fullmatch(r"Q[1-4]", x)))
            ).any():
                raise ResultValidationError(
                    f"movement.{col} contains an unsupported value"
                )
    else:
        if out.duplicated(["entity", period, "from_quadrant", "to_quadrant"]).any():
            raise ResultValidationError(
                "transitions contain duplicate transition identities"
            )
        if (
            ~out["from_quadrant"]
            .astype(str)
            .map(lambda x: bool(re.fullmatch(r"Q[1-4]", x)))
        ).any():
            raise ResultValidationError(
                "transitions.from_quadrant contains an unsupported value"
            )
        if (
            ~out["to_quadrant"].astype(str).map(lambda x: bool(_QUADRANT.fullmatch(x)))
        ).any():
            raise ResultValidationError(
                "transitions.to_quadrant contains an unsupported value"
            )
        if (~out["risk_level"].isin(_RISK)).any():
            raise ResultValidationError(
                "transitions.risk_level contains an unsupported value"
            )
    # Every value must be a JSON scalar; reject hidden non-finite extras too.
    _json_check(_table_to_dict(out), role)
    return out


def _json_check(value: Any, name: str) -> None:
    """Validate portable metadata/table values without serialising arbitrary objects."""
    if value is None or isinstance(value, (str, bool, int)):
        return
    if isinstance(value, float) and math.isfinite(value):
        return
    if isinstance(value, list):
        for item in value:
            _json_check(item, name)
        return
    if isinstance(value, dict) and all(isinstance(k, str) for k in value):
        for item in value.values():
            _json_check(item, name)
        return
    raise ResultValidationError(f"{name} must contain finite JSON values")


def _table_to_dict(frame: pd.DataFrame | None) -> dict[str, Any] | None:
    if frame is None:
        return None
    records = frame.astype(object).where(frame.notna(), None).to_dict(orient="records")
    # pandas treats infinity as non-missing; NaN represents a nullable frame cell.
    return {"columns": [str(c) for c in frame.columns], "records": records}


def _table_from_dict(value: Any, role: str, cadence: str) -> pd.DataFrame | None:
    if value is None:
        return None
    if isinstance(value, dict) and set(value) != {"columns", "records"}:
        raise ResultValidationError(f"{role} table requires only columns and records")
    if (
        not isinstance(value, dict)
        or not isinstance(value.get("columns"), list)
        or not isinstance(value.get("records"), list)
    ):
        raise ResultValidationError(
            f"{role} table must contain columns and records lists"
        )
    columns = value["columns"]
    if any(not isinstance(c, str) or not c for c in columns) or len(columns) != len(
        set(columns)
    ):
        raise ResultValidationError(f"{role} table has invalid columns")
    for row in value["records"]:
        if not isinstance(row, dict) or set(row) != set(columns):
            raise ResultValidationError(
                f"{role} records must match their columns exactly"
            )
    _json_check(value, role)
    try:
        frame = pd.DataFrame(value["records"], columns=columns)
    except Exception as exc:  # pragma: no cover - pandas error wording varies
        raise ResultValidationError(f"invalid {role} records") from exc
    return _clean_frame(frame, role, cadence)


@dataclass
class ResultDataset:
    """One entity type and cadence of saved analytical tables."""

    entity_type: str
    cadence: str
    source_id: str
    coverage_start: str
    as_of: str
    type_label: str | None = None
    matrix: pd.DataFrame | None = None
    movement: pd.DataFrame | None = None
    transitions: pd.DataFrame | None = None
    selections: dict[str, Any] = field(default_factory=dict)
    source_hashes: dict[str, str] = field(default_factory=dict)
    source_files: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.entity_type, str) or not self.entity_type.strip():
            raise ResultValidationError("entity_type must be a non-empty string")
        if not isinstance(self.cadence, str) or self.cadence not in _PERIOD:
            raise ResultValidationError("cadence must be 'monthly' or 'quarterly'")
        for name, value in (
            ("source_id", self.source_id),
            ("coverage_start", self.coverage_start),
            ("as_of", self.as_of),
        ):
            if not isinstance(value, str) or not value.strip():
                raise ResultValidationError(f"{name} must be a non-empty string")
        if not _PERIOD[self.cadence].fullmatch(self.coverage_start) or not _PERIOD[
            self.cadence
        ].fullmatch(self.as_of):
            raise ResultValidationError(
                "coverage_start and as_of must use canonical cadence labels"
            )
        if self.coverage_start > self.as_of:
            raise ResultValidationError("coverage_start cannot be after as_of")
        if self.type_label is not None and (
            not isinstance(self.type_label, str) or not self.type_label.strip()
        ):
            raise ResultValidationError("type_label must be a non-empty string or null")
        if (
            not isinstance(self.selections, dict)
            or not isinstance(self.source_hashes, dict)
            or not isinstance(self.source_files, dict)
        ):
            raise ResultValidationError(
                "selections, source_hashes and source_files must be objects"
            )
        _json_check(self.selections, "selections")
        for role, digest in self.source_hashes.items():
            if (
                role not in _ROLE_COLUMNS
                or not isinstance(digest, str)
                or not re.fullmatch(r"[0-9a-f]{64}", digest)
            ):
                raise ResultValidationError(
                    "source_hashes must map table roles to SHA-256 hex digests"
                )
        for role, name in self.source_files.items():
            if (
                role not in _ROLE_COLUMNS
                or not isinstance(name, str)
                or not name
                or name in {".", ".."}
                or "/" in name
                or "\\" in name
            ):
                raise ResultValidationError(
                    "source_files must map table roles to basenames only"
                )
        for role in ("matrix", "movement", "transitions"):
            frame = getattr(self, role)
            if frame is not None:
                setattr(self, role, _clean_frame(frame, role, self.cadence))
                if role != "matrix":
                    period = _period_column(frame, self.cadence, role)
                    if (
                        (frame[period] < self.coverage_start)
                        | (frame[period] > self.as_of)
                    ).any():
                        raise ResultValidationError(
                            f"{role} periods lie outside coverage_start/as_of"
                        )
        if self.movement is not None and self.transitions is not None:
            mp = _period_column(self.movement, self.cadence, "movement")
            tp = _period_column(self.transitions, self.cadence, "transitions")
            available = set(zip(self.movement["entity"], self.movement[mp]))
            if any(
                (row["entity"], row[tp]) not in available
                for _, row in self.transitions.iterrows()
            ):
                raise ResultValidationError(
                    "each transition must match an entity/period in movement"
                )

    def to_dict(self) -> dict[str, Any]:
        return {
            "entity_type": self.entity_type,
            "cadence": self.cadence,
            "source_id": self.source_id,
            "coverage_start": self.coverage_start,
            "as_of": self.as_of,
            "type_label": self.type_label,
            "matrix": _table_to_dict(self.matrix),
            "movement": _table_to_dict(self.movement),
            "transitions": _table_to_dict(self.transitions),
            "selections": self.selections,
            "source_hashes": self.source_hashes,
            "source_files": self.source_files,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "ResultDataset":
        if not isinstance(value, Mapping):
            raise ResultValidationError("dataset must be an object")
        fields = set(cls.__dataclass_fields__)
        if set(value) - fields:
            raise ResultValidationError(
                f"unknown dataset fields: {sorted(set(value) - fields)}"
            )
        cadence = value.get("cadence")
        if not isinstance(cadence, str) or cadence not in _PERIOD:
            raise ResultValidationError("cadence must be 'monthly' or 'quarterly'")
        return cls(
            entity_type=value.get("entity_type"),
            cadence=cadence,
            source_id=value.get("source_id"),
            coverage_start=value.get("coverage_start"),
            as_of=value.get("as_of"),
            type_label=value.get("type_label"),
            matrix=_table_from_dict(value.get("matrix"), "matrix", cadence),
            movement=_table_from_dict(value.get("movement"), "movement", cadence),
            transitions=_table_from_dict(
                value.get("transitions"), "transitions", cadence
            ),
            selections=value.get("selections", {}),
            source_hashes=value.get("source_hashes", {}),
            source_files=value.get("source_files", {}),
        )


@dataclass
class ResultBundle:
    """A deterministic, JSON-serialisable collection of result datasets."""

    datasets: list[ResultDataset] = field(default_factory=list)
    producer_version: str = __version__
    schema_version: int = SCHEMA_VERSION

    def __post_init__(self) -> None:
        if (
            type(self.schema_version) is not int
            or self.schema_version != SCHEMA_VERSION
        ):
            raise ResultValidationError(
                f"unsupported schema_version: {self.schema_version}"
            )
        if not isinstance(self.datasets, list) or any(
            not isinstance(d, ResultDataset) for d in self.datasets
        ):
            raise ResultValidationError(
                "datasets must be a list of ResultDataset objects"
            )
        if (
            not isinstance(self.producer_version, str)
            or not self.producer_version.strip()
        ):
            raise ResultValidationError("producer_version must be a non-empty string")
        keys = [(d.entity_type, d.cadence) for d in self.datasets]
        if len(keys) != len(set(keys)):
            raise ResultValidationError("duplicate entity_type/cadence dataset")

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "producer_version": self.producer_version,
            "datasets": [d.to_dict() for d in self.datasets],
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "ResultBundle":
        if not isinstance(value, Mapping) or not isinstance(
            value.get("datasets"), list
        ):
            raise ResultValidationError("bundle must contain a datasets list")
        if set(value) - {"schema_version", "producer_version", "datasets"}:
            raise ResultValidationError("unknown result bundle fields")
        return cls(
            datasets=[ResultDataset.from_dict(x) for x in value["datasets"]],
            producer_version=value.get("producer_version", "unknown"),
            schema_version=value.get("schema_version"),
        )

    def save(self, path: str | Path) -> None:
        # Revalidate mutable DataFrames/settings before exporting.
        validated = self.from_dict(self.to_dict())
        Path(path).write_text(
            json.dumps(
                validated.to_dict(),
                ensure_ascii=False,
                sort_keys=True,
                indent=2,
                allow_nan=False,
            )
            + "\n",
            encoding="utf-8",
        )

    @classmethod
    def load(cls, path: str | Path) -> "ResultBundle":
        try:
            value = strict_json_loads(Path(path).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise ResultValidationError(f"invalid result bundle JSON: {exc}") from exc
        return cls.from_dict(value)


def import_results_csv(
    *,
    entity_type: str,
    cadence: str,
    source_id: str,
    coverage_start: str,
    as_of: str,
    matrix_path: str | Path | None = None,
    movement_path: str | Path | None = None,
    transitions_path: str | Path | None = None,
    matrix: pd.DataFrame | None = None,
    movement: pd.DataFrame | None = None,
    transitions: pd.DataFrame | None = None,
    files: Mapping[str, str | Path] | None = None,
    type_label: str | None = None,
    selections: dict[str, Any] | None = None,
) -> ResultDataset:
    """Import explicitly named role CSVs; filenames are never interpreted."""
    frames: dict[str, pd.DataFrame | None] = {}
    hashes: dict[str, str] = {}
    names: dict[str, str] = {}
    paths: dict[str, str | Path | None] = {
        "matrix": matrix_path,
        "movement": movement_path,
        "transitions": transitions_path,
    }
    if files is not None:
        if not isinstance(files, Mapping) or any(
            role not in _ROLE_COLUMNS for role in files
        ):
            raise ResultValidationError(
                "files must map matrix, movement and transitions roles"
            )
        for role, path in files.items():
            if paths[role] is not None:
                raise ResultValidationError(f"provide {role} only once")
            paths[role] = path
    supplied_frames = {
        "matrix": matrix,
        "movement": movement,
        "transitions": transitions,
    }
    for role, path in (
        ("matrix", paths["matrix"]),
        ("movement", paths["movement"]),
        ("transitions", paths["transitions"]),
    ):
        if path is None:
            frames[role] = supplied_frames[role]
            continue
        if supplied_frames[role] is not None:
            raise ResultValidationError(
                f"provide either {role}_path or {role} frame, not both"
            )
        path = Path(path)
        try:
            contents = path.read_bytes()
            text = contents.decode("utf-8-sig")
            reader = csv.reader(io.StringIO(text), strict=True)
            header = next(reader, [])
            if (
                not header
                or len(header) != len(set(header))
                or any(not c for c in header)
            ):
                raise ResultValidationError(
                    f"{role} CSV requires unique non-empty headers"
                )
            for line_number, row in enumerate(reader, start=2):
                if row and len(row) != len(header):
                    raise ResultValidationError(
                        f"{role} CSV row {line_number} has {len(row)} fields; "
                        f"expected {len(header)}"
                    )
            frame = pd.read_csv(
                io.StringIO(text), dtype=str, keep_default_na=False, na_filter=False
            )
        except (OSError, ValueError, UnicodeError, csv.Error) as exc:
            raise ResultValidationError(f"cannot read {role} CSV: {exc}") from exc
        # Numeric conversion is restricted to known analytical columns; IDs remain lexical.
        for col in _NUMERIC[role] & set(frame.columns):
            frame[col] = frame[col].replace("", pd.NA)
            try:
                frame[col] = pd.to_numeric(frame[col], errors="raise")
            except (ValueError, TypeError) as exc:
                raise ResultValidationError(
                    f"{role}.{col} contains non-numeric values"
                ) from exc
        frames[role] = frame
        hashes[role] = hashlib.sha256(contents).hexdigest()
        names[role] = path.name
    return ResultDataset(
        entity_type=entity_type,
        cadence=cadence,
        source_id=source_id,
        coverage_start=coverage_start,
        as_of=as_of,
        type_label=type_label,
        selections=selections if selections is not None else {},
        source_hashes=hashes,
        source_files=names,
        **frames,
    )
