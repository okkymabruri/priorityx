"""Request fingerprints and compatible artifact naming."""

from pathlib import Path
import re

import pandas as pd
import pytest

from priorityx.utils.helpers import (
    compute_cache_key,
    generate_output_path,
    latest_artifact_csv,
    save_dataframe_to_csv,
)
from test_results import frames


@pytest.mark.parametrize("change", ["value", "column", "dtype", "index", "rows", "columns", "index_name"])
def test_cache_key_tracks_data_and_schema(change):
    matrix = frames()[0]
    matrix = pd.concat([matrix, matrix.assign(entity="002")], ignore_index=True)
    original = matrix.copy(deep=True)
    altered = matrix.copy(deep=True)
    if change == "value":
        altered.loc[0, "x_score"] += .25
    elif change == "column":
        altered = altered.rename(columns={"count": "events"})
    elif change == "dtype":
        altered["count"] = altered["count"].astype(float)
    elif change == "index":
        altered.index = [10, 11]
    elif change == "rows":
        altered = altered.iloc[::-1]
    elif change == "columns":
        altered = altered[altered.columns[::-1]]
    elif change == "index_name":
        altered.index.name = "row"
    assert compute_cache_key(matrix, {}) != compute_cache_key(altered, {})
    pd.testing.assert_frame_equal(matrix, original)


def test_cache_key_settings_order_version_and_object_types():
    matrix = frames()[0]
    key = compute_cache_key(matrix, {"threshold": 20, "priors": {"x": 3.5, "y": 3.0}}, version="a")
    assert re.fullmatch(r"[0-9a-f]{16}", key)
    assert key == compute_cache_key(matrix, {"priors": {"y": 3.0, "x": 3.5}, "threshold": 20}, version="a")
    assert key != compute_cache_key(matrix, {"threshold": 20, "priors": {"x": 3.5, "y": 3.0}}, version="b")
    numeric = matrix.astype(object)
    text = numeric.copy()
    text["x_score"] = text["x_score"].map(str)
    assert compute_cache_key(numeric, {}) != compute_cache_key(text, {})
    categories = matrix.astype({"quadrant": "category"})
    changed = categories.copy()
    changed["quadrant"] = changed["quadrant"].cat.add_categories("Q2")
    assert compute_cache_key(categories, {}) != compute_cache_key(changed, {})


def test_cache_key_rejects_unsupported_inputs():
    matrix = frames()[0]
    with pytest.raises(ValueError, match="Cannot fingerprint"):
        compute_cache_key(matrix.assign(extra=[[1, 2]]), {})
    with pytest.raises(ValueError, match="Cannot fingerprint"):
        compute_cache_key(matrix, {"prior": float("inf")})


@pytest.mark.parametrize("cadence,suffix", [("quarterly", "Q"), ("monthly", "M"), ("yearly", "Y"), ("semiannual", "S")])
def test_artifact_helpers_keep_keyed_and_date_only_lookups_separate(tmp_path, cadence, suffix):
    matrix = frames()[0]
    key = compute_cache_key(matrix, {"cadence": cadence})
    options = dict(artifact="movement", entity_name="Service", temporal_granularity=cadence, output_dir=str(tmp_path))
    dated = save_dataframe_to_csv(matrix, **options)
    keyed = save_dataframe_to_csv(matrix, **options, key=key)
    assert re.fullmatch(f"movement-service-{suffix}-[0-9]{{8}}.csv", Path(dated).name)
    assert Path(keyed).name == f"movement-service-{suffix}-{key}.csv"
    assert generate_output_path(**options, key=key) == keyed
    assert latest_artifact_csv(**options) == dated
    assert latest_artifact_csv(**options, key=key) == keyed
    assert latest_artifact_csv(**options, key="f" * 16) is None
    assert latest_artifact_csv("movement", "Service", str(tmp_path), key=key) == keyed
    assert latest_artifact_csv("movement", "Service", str(tmp_path)) == dated
    assert sorted(path.suffix for path in tmp_path.iterdir()) == [".csv", ".csv"]


@pytest.mark.parametrize("key", ["../bad", "a" * 8, "A" * 16])
def test_artifact_helpers_reject_invalid_keys(tmp_path, key):
    with pytest.raises(ValueError, match="Cache key"):
        generate_output_path("movement", "Service", output_dir=str(tmp_path), key=key)
    with pytest.raises(ValueError, match="Cache key"):
        latest_artifact_csv("movement", "Service", str(tmp_path), key=key)
