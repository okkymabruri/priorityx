import json

import pandas as pd
import pytest

from priorityx import __version__
from priorityx.results import (
    ResultBundle,
    ResultDataset,
    ResultValidationError,
    import_results_csv,
)


def frames(cadence="monthly"):
    period = "2025-01" if cadence == "monthly" else "2025-Q1"
    return (
        pd.DataFrame(
            {
                "entity": ["001"],
                "x_score": [1.0],
                "y_score": [2.0],
                "count": [3],
                "quadrant": ["Q1"],
            }
        ),
        pd.DataFrame(
            {
                "entity": ["001"],
                "month" if cadence == "monthly" else "quarter": [period],
                "period_x": [1.0],
                "period_y": [2.0],
                "period_quadrant": ["Q1"],
                "global_quadrant": ["Q1"],
            }
        ),
        pd.DataFrame(
            {
                "entity": ["001"],
                "transition_quarter": [period],
                "from_quadrant": ["Q2"],
                "to_quadrant": ["Q1*XY"],
                "risk_level": ["critical"],
            }
        ),
    )


@pytest.mark.parametrize("cadence", ["monthly", "quarterly"])
def test_bundle_roundtrip_preserves_empty_schema_and_string_ids(tmp_path, cadence):
    matrix, movement, transitions = frames(cadence)
    first = "2025-01" if cadence == "monthly" else "2025-Q1"
    last = "2025-12" if cadence == "monthly" else "2025-Q4"
    empty = pd.DataFrame(
        columns=[
            "entity",
            "month",
            "period_x",
            "period_y",
            "period_quadrant",
            "global_quadrant",
        ]
    )
    d = ResultDataset(
        "item",
        cadence,
        "source",
        first,
        last,
        type_label="Work units",
        matrix=matrix,
        movement=movement,
        transitions=transitions,
    )
    b = ResultBundle([d])
    assert b.producer_version == __version__
    path = tmp_path / "bundle.json"
    b.save(path)
    loaded = ResultBundle.load(path)
    assert loaded.datasets[0].entity_type == "item"
    assert loaded.datasets[0].type_label == "Work units"
    assert loaded.datasets[0].matrix.iloc[0]["entity"] == "001"
    assert loaded.datasets[0].movement.equals(movement)
    assert loaded.producer_version == __version__
    # Opening older results retains their actual producer, not this install's version.
    historical = {**loaded.to_dict(), "producer_version": "0.5.0"}
    assert ResultBundle.from_dict(historical).producer_version == "0.5.0"
    empty_dataset = ResultDataset(
        "empty", "monthly", "s", "2025-01", "2025-12", movement=empty
    )
    empty_path = tmp_path / "empty.json"
    ResultBundle([empty_dataset]).save(empty_path)
    restored_empty = ResultBundle.load(empty_path).datasets[0]
    assert restored_empty.movement.empty
    assert restored_empty.movement.columns.tolist() == empty.columns.tolist()
    assert (
        ResultDataset(
            "group", "monthly", "source", "2025-01", "2025-12", movement=empty
        ).movement.columns.tolist()
        == empty.columns.tolist()
    )


def test_missing_tables_are_unavailable_and_csv_hashes_are_portable(tmp_path):
    matrix, movement, _ = frames()
    mp = tmp_path / "matrix.csv"
    movement_path = tmp_path / "movement.csv"
    matrix.to_csv(mp, index=False)
    movement.to_csv(movement_path, index=False)
    d = import_results_csv(
        entity_type="item",
        cadence="monthly",
        source_id="s",
        coverage_start="2025-01",
        as_of="2025-12",
        matrix_path=mp,
        movement_path=movement_path,
    )
    assert d.transitions is None
    assert set(d.source_hashes) == {"matrix", "movement"}
    assert d.matrix.iloc[0]["entity"] == "001"


@pytest.mark.parametrize(
    "kwargs",
    [
        {"cadence": "monthly", "coverage_start": "2025-Q1", "as_of": "2025-12"},
        {"cadence": "quarterly", "coverage_start": "2025-Q2", "as_of": "2025-Q1"},
    ],
)
def test_invalid_period_metadata_rejected(kwargs):
    with pytest.raises(ResultValidationError):
        ResultDataset(
            "item",
            source_id="s",
            matrix=None,
            movement=None,
            transitions=None,
            type_label=None,
            **kwargs,
        )


def test_duplicates_nonfinite_and_schema_errors_rejected():
    matrix, _, _ = frames()
    with pytest.raises(ResultValidationError):
        ResultDataset(
            "item",
            "monthly",
            "s",
            "2025-01",
            "2025-12",
            matrix=pd.concat([matrix, matrix]),
        )
    bad = matrix.copy()
    bad.loc[0, "x_score"] = float("inf")
    with pytest.raises(ResultValidationError):
        ResultDataset("item", "monthly", "s", "2025-01", "2025-12", matrix=bad)
    with pytest.raises(ResultValidationError):
        ResultBundle.from_dict(
            {"schema_version": 99, "producer_version": "x", "datasets": []}
        )
    with pytest.raises(ResultValidationError):
        ResultBundle.from_dict(json.loads('{"schema_version":1,"datasets":{}}'))


def test_full_history_and_independent_populations_are_allowed():
    matrix, movement, transitions = frames()
    movement = pd.concat([movement, movement.assign(month="2025-02")])
    d = ResultDataset(
        "item",
        "monthly",
        "s",
        "2025-01",
        "2025-12",
        matrix=matrix.assign(entity="separate-matrix-member"),
        movement=movement,
        transitions=transitions,
    )
    assert len(d.movement) == 2
    assert d.matrix.entity.tolist() == ["separate-matrix-member"]


def test_numeric_frames_are_normalized_and_csv_ids_stay_lexical(tmp_path):
    matrix, _, _ = frames()
    matrix = pd.concat([matrix, matrix.assign(entity="NA")], ignore_index=True)
    matrix["x_score"] = matrix.x_score.astype(str)
    dataset = ResultDataset(
        "item", "monthly", "s", "2025-01", "2025-12", matrix=matrix
    )
    assert dataset.to_dict()["matrix"]["records"][0]["x_score"] == 1.0
    path = tmp_path / "matrix.csv"
    matrix.to_csv(path, index=False)
    loaded = import_results_csv(
        entity_type="item",
        cadence="monthly",
        source_id="s",
        coverage_start="2025-01",
        as_of="2025-12",
        matrix_path=path,
    )
    assert loaded.matrix.entity.tolist() == ["001", "NA"]


def test_duplicate_csv_headers_and_unknown_schema_fields_are_errors(tmp_path):
    path = tmp_path / "duplicate.csv"
    path.write_text("entity,x_score,x_score,y_score,count,quadrant\n001,1,9,2,3,Q1\n")
    with pytest.raises(ResultValidationError, match="headers"):
        import_results_csv(
            entity_type="item",
            cadence="monthly",
            source_id="s",
            coverage_start="2025-01",
            as_of="2025-12",
            matrix_path=path,
        )
    matrix, _, _ = frames()
    payload = ResultBundle(
        [ResultDataset("item", "monthly", "s", "2025-01", "2025-12", matrix=matrix)]
    ).to_dict()
    for location in (payload, payload["datasets"][0], payload["datasets"][0]["matrix"]):
        location["unknown"] = None
        with pytest.raises(ResultValidationError):
            ResultBundle.from_dict(payload)
        del location["unknown"]


@pytest.mark.parametrize("row", ["DROPPED,001,1,2,3,Q1", "001,1,2,3"])
def test_csv_row_width_cannot_shift_or_pad_saved_values(tmp_path, row):
    path = tmp_path / "invalid.csv"
    path.write_text("entity,x_score,y_score,count,quadrant\n" + row + "\n")
    with pytest.raises(ResultValidationError, match="fields"):
        import_results_csv(
            entity_type="item",
            cadence="monthly",
            source_id="s",
            coverage_start="2025-01",
            as_of="2025-12",
            matrix_path=path,
        )


def test_bounds_cross_table_consistency_and_mutation_are_validated(tmp_path):
    matrix, movement, transitions = frames()
    with pytest.raises(ResultValidationError, match="outside"):
        ResultDataset("item", "monthly", "s", "2025-02", "2025-12", movement=movement)
    with pytest.raises(ResultValidationError, match="match"):
        ResultDataset(
            "item",
            "monthly",
            "s",
            "2025-01",
            "2025-12",
            movement=movement,
            transitions=transitions.assign(entity="missing"),
        )
    dataset = ResultDataset(
        "item", "monthly", "s", "2025-01", "2025-12", matrix=matrix
    )
    dataset.matrix.loc[0, "count"] = -1
    with pytest.raises(ResultValidationError, match="non-negative"):
        ResultBundle([dataset]).save(tmp_path / "invalid.json")
