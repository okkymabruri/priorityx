# Saved result bundles

`priorityx.results` provides a small, portable interchange format for the local
visualisation application. A `ResultDataset` identifies one entity type and
cadence (`monthly` or `quarterly`) and can contain independent matrix, movement
and transition tables. A missing table is represented by `null`; an empty table
retains its column schema.

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

CSV roles are passed explicitly; filenames are never inferred. Identifiers are
read as strings (so values such as `001` remain unchanged), while known numeric
columns are validated for finite values and non-negative integer counts. Full
movement history is retained. The JSON schema is versioned (`schema_version: 1`)
and records table columns plus records, with no pickle, executable code or
absolute paths.

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
