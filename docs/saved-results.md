# Saved result bundles

`priorityx.results` provides a small, portable interchange format for the local
visualisation application. A `ResultDataset` identifies one entity type and
cadence (`monthly` or `quarterly`) and can contain independent matrix, movement
and transition tables. A missing table is represented by `null`; an empty table
retains its column schema.

## Build and open a bundle

Use your own saved file paths and actual coverage periods:

```python
from priorityx.results import ResultBundle, import_results_csv

dataset = import_results_csv(
    entity_type="entity", cadence="monthly", source_id="saved-results-2026",
    coverage_start="2025-01", as_of="2026-09",
    matrix_path="priority_matrix.csv", movement_path="movement.csv",
    transitions_path="transitions.csv",
)
ResultBundle([dataset]).save("results.json")
bundle = ResultBundle.load("results.json")
```

```sh
python -m priorityx app --bundle results.json
```

The files are analytical outputs: the matrix from `fit_priority_matrix()`,
movement from `track_movement()`, and transitions from `extract_transitions()`.
The library returns DataFrames by default. Save the full tables explicitly with
`matrix.to_csv("priority_matrix.csv", index=False)` and the corresponding
movement/transition filenames, or pass existing DataFrames directly to
`import_results_csv(matrix=matrix, movement=movement, transitions=transitions, ...)`.
Do not substitute a plot's filtered trajectory/timeline CSV for full history.

An empty transition result still needs the required header columns below.
If there is no transition table, omit `transitions_path`; the app will mark the
timeline unavailable. Neither case requires inventing events.

## Required columns

Each supplied table must contain these columns. A missing table is allowed.

| Saved CSV role | Identity shown and linked | Period column | Other required columns |
|---|---|---|---|
| Matrix | `entity` | None; bundle `as_of` dates the snapshot | `x_score`, `y_score`, `count`, `quadrant` |
| Movement, Quarterly | `entity` | `quarter`, e.g. `2025-Q1` | `period_x`, `period_y`, `period_quadrant`, `global_quadrant` |
| Movement, Monthly | `entity` | `month`, e.g. `2025-01`; legacy `quarter` with monthly values is also accepted | Same movement columns |
| Transitions, Quarterly | `entity` | `transition_quarter`, e.g. `2025-Q1` | `from_quadrant`, `to_quadrant`, `risk_level` |
| Transitions, Monthly | `entity` | `transition_month` or legacy `transition_quarter`, with `YYYY-MM` values | Same transition columns |

Use only one accepted period column per table; supplying both aliases is
ambiguous and rejected. `track_movement()` returns its canonical `quarter`
column even for Monthly, while saved monthly tables may use `month`.
`extract_transitions()` uses `transition_quarter` for both cadences.

`entity` must be a nonempty string, identical across tables for the same entity.
It is both the chart label and linkage key; an extra `name` column is retained
as metadata but does not replace the displayed identifier. To show names instead
of codes, explicitly map every table's `entity` to the same unique names before
creating the bundle. Preserve the original code in an extra column if needed;
do not merge different identities under a duplicate name.

Scores must be finite numbers; `count` is a non-negative integer. Matrix and
movement quadrants are `Q1`–`Q4`. Transition `from_quadrant` uses `Q1`–`Q4`;
`to_quadrant` also accepts `*X`, `*Y` or `*XY` suffixes. Supported `risk_level`
values are `critical`, `high`, `medium`, `low`, `stable` (case-sensitive).
For existing event-class/spike preparation, retain `cumulative_count` in movement
when available; without it event colors use the documented Investigate fallback.
Additional known numeric fields include movement's `global_x`, `global_y`,
`count_total`, `x_delta`, `y_delta`, `period_count`, `cumulative_count` and
transitions' `volume_change`, `growth_change`. Optional delta/period-count fields
may be empty; required scores and counts may not.

Quarterly periods use exactly `YYYY-Q1` through `YYYY-Q4`, Monthly exactly
`YYYY-MM`. A date such as `2025-03-31` is not a saved period label. Both
`coverage_start` and `as_of` must use the chosen cadence's format, in order, and
all movement/transition periods must lie within them. When both tables are
supplied, each transition must match an existing movement entity/period.
Matrix identifiers must be unique, movement entity/period pairs unique, and
transition entity/period/from/to combinations unique. Matrix and movement
populations may legitimately differ.

## Map existing result columns

The importer does not expose `entity_col` or `timestamp_col`: it expects the
saved schema above. Rename the identifier and period columns explicitly in your
adapter. This example starts with **already calculated result CSVs**, not raw
events; score/quadrant columns are retained unchanged:

```python
import pandas as pd
from priorityx.results import ResultBundle, import_results_csv

matrix = pd.read_csv("saved_matrix.csv", dtype={"unit_id": str})
movement = pd.read_csv("saved_movement.csv", dtype={"unit_id": str})
transitions = pd.read_csv("saved_transitions.csv", dtype={"unit_id": str})

matrix = matrix.rename(columns={"unit_id": "entity"})
movement = movement.rename(columns={"unit_id": "entity", "period": "quarter"})
transitions = transitions.rename(
    columns={"unit_id": "entity", "event_period": "transition_quarter"}
)

dataset = import_results_csv(
    entity_type="work_unit", type_label="Work units", cadence="quarterly",
    source_id="saved-analysis", coverage_start="2025-Q1", as_of="2025-Q4",
    matrix=matrix, movement=movement, transitions=transitions,
)
ResultBundle([dataset]).save("results.json")
```

Here `period` and `event_period` already contain `YYYY-Qn` labels. If your saved
result uses dates **inside the represented period**, convert deliberately, for example
`pd.to_datetime(movement["quarter"], errors="raise").dt.to_period("Q").astype(str).str.replace("Q", "-Q", regex=False)`.
For Monthly use `.dt.to_period("M").astype(str)` and the `month` column.
For an exclusive cutoff date, first identify the represented period: `2025-04-01`
can mean the end of Q1, even though that date falls in Q2. Convert the represented
period end, not the boundary blindly; keep the same interpretation across tables.
Check that conversion has not collapsed two saved rows into one entity/period;
the validator rejects duplicates. Do not aggregate or change scores to make an
import pass. Reading an identifier as a string preserves `001`; converting an
already parsed integer back to text cannot restore lost leading zeros.

For raw-event analysis, keep your own source headers and pass their names to
the existing [analysis API](quickstart.md):

```python
import pandas as pd
import priorityx as px

events = pd.read_csv("events.csv", dtype={"unit_id": str})
events["observed_at"] = pd.to_datetime(events["observed_at"], errors="raise")
# These run analysis; they are not AutoViz import or layout controls:
# matrix = px.fit_priority_matrix(events, entity_col="unit_id",
#     timestamp_col="observed_at", temporal_granularity="quarterly")
# movement = px.track_movement(events, entity_col="unit_id",
#     timestamp_col="observed_at", temporal_granularity="quarterly")
```

## Validation and provenance

CSV roles are passed explicitly; filenames are never inferred. Identifiers are
read as strings (so values such as `001` remain unchanged), while known numeric
columns are validated for finite values and non-negative integer counts. Full
movement history is retained. The JSON schema is versioned (`schema_version: 1`)
and records table columns plus records, without pickle or serialized Python
objects. Recorded source filenames are basenames, not absolute paths.
Caller-supplied metadata and extra table columns are retained, so review them
before sharing a bundle or offline HTML; arbitrary metadata is not scrubbed.

`entity_type` and the optional `type_label` are caller-defined; PriorityX does not
reserve domain categories. This importer accepts PriorityX's generic result
columns. Source-specific raw columns and transformations belong in the caller's
adapter before import; no source schema is inferred or built into the package.

Unknown bundle/dataset schema fields and duplicate JSON fields are rejected.
Additional CSV table columns are retained as caller metadata; PriorityX does not
guess their meaning. The [local workspace](app.md) uses the same import validator.

Optional `selections` keys control saved display choices: `timeline_entities`
and `trajectory_entities` are ordered unique identifier lists,
`timeline_risk_levels` filters saved transition risks, `timeline_start_period`
sets an explicit canonical display cutoff, and `trajectory_periods` selects the
recent path window (1–120 periods). These choices never replace the full tables.
Timeline classes and suffixes are prepared using full saved movement history.

An explicit `trajectory_entities` list wins, including its order and an empty
list. When it is absent, both renderers select up to three entities with saved
points in the recent path window: 12 months or eight quarters by default.
Selection ranks the sum of absolute consecutive changes in `period_y`, descending.
Changes are calculated over full saved history before selecting the window, so
the change into its first period is included when an earlier point exists.
Ties use the exact entity identifier in ascending order; input row order does
not decide the selection. A single saved point contributes zero movement.
The optional `y_delta` column is not required, and source tables remain unchanged.
