# PriorityX Output Naming

This note documents where PriorityX writes plots/CSVs and how filenames
are constructed. It is meant as a quick reference when wiring outputs
into downstream pipelines or BI tools.

---

## Directories

By default, PriorityX writes artifacts under the current working directory, using two main folders:

- `results/plot/` — PNG plots
- `results/csv/` — CSV tables (movement, matrices, transitions, etc.)

You can override these via the `plot_dir` / `csv_dir` / `output_dir`
arguments on the plotting and helper functions.

Note: repository examples may override these directories (e.g., to write artifacts under `examples/<name>/results/`).

---

## Priority Matrix

Function: `priorityx.viz.matrix.plot_priority_matrix`

- Default `plot_dir`: `results/plot`
- Default `csv_dir`: `results/csv`
- Filename pattern (plot):

  ```text
  priority_matrix-<entity_name_slug>-<granularity_suffix>-<YYYYMMDD>.png
  ```

- Filename pattern (CSV):

  ```text
  priority_matrix-<entity_name_slug>-<granularity_suffix>-<YYYYMMDD>.csv
  ```

Where:

- `<entity_name_slug>` is `entity_name.lower().replace(" ", "_")`
- `<granularity_suffix>` is:
  - `Q` for quarterly
  - `Y` for yearly
  - `S` for semiannual

Example (generic entity, quarterly):

```text
results/plot/priority_matrix-entity-Q-20251126.png
results/csv/priority_matrix-entity-Q-20251126.csv
```

---

## Transition Timelines

Function: `priorityx.viz.timeline.plot_transition_timeline`

- Default `plot_dir`: `results/plot`
- Default `csv_dir`: `results/csv`
- Filename pattern (plot):

  ```text
  transition_timeline-<entity_name_slug>-<granularity_suffix>-<YYYYMMDD>.png
  ```

- Filename pattern (CSV):

  ```text
  transition_timeline-<entity_name_slug>-<granularity_suffix>-<YYYYMMDD>.csv
  ```

Example (generic entity, quarterly):

```text
results/plot/transition_timeline-entity-Q-20251126.png
results/csv/transition_timeline-entity-Q-20251126.csv
```

---

## Trajectories

Function: `priorityx.viz.trajectory.plot_entity_trajectories`

- Default `plot_dir`: `results/plot`
- Default `csv_dir`: `results/csv`
- Filename pattern (plot):

  ```text
  trajectories-<entity_name_slug>-<granularity_suffix>-<YYYYMMDD>.png
  ```

- When `save_csv=True` (default is `False`), CSV is saved via
  `priorityx.utils.helpers.save_dataframe_to_csv` with artifact name
  `"trajectories"` (see next section).

Example (generic entity, quarterly):

```text
results/plot/trajectories-entity-Q-20251126.png
results/csv/trajectories-entity-Q-20251126.csv   # only when save_csv=True
```

---

## Helpers: CSV Naming

Utility: `priorityx.utils.helpers.save_dataframe_to_csv`

This helper centralises CSV naming using `generate_output_path`:

```text
<output_dir>/<artifact>-<entity_slug>-<granularity_suffix>-<YYYYMMDD>.csv
```

Where:

- `<output_dir>` defaults to `results/csv`
- `<artifact>` is a short key such as `movement`, `trajectories`,
  `priority_matrix`
- `<entity_slug>` is `entity_name.lower().replace(" ", "_")`
- `<granularity_suffix>` is `Q`, `Y`, or `S` (as above)

Examples:

```text
results/csv/movement-entity-Q-20251126.csv
results/csv/trajectories-entity-Q-20251126.csv
```

### Downstream pipeline outputs

Downstream applications may define their own canonical artifact set. PriorityX
does not infer or reserve source-specific filenames; pass explicit paths when a
caller needs a particular naming convention. The generic result roles are:

```text
movement-*.csv
priority_matrix-*.csv
transitions-*.csv
```

Trajectory CSVs (`trajectories-*.csv`) are optional and are written only when a
caller passes `save_csv=True` to `plot_entity_trajectories`.

---

## Overriding locations

All plotting and helper functions accept directories as keyword arguments
(`plot_dir`, `csv_dir`, `output_dir`). A caller can pass explicit paths for its
own workspace, for example:

```python
plot_priority_matrix(
    results_df,
    entity_name="Entity",
    plot_dir="workspace/results/plot",
    csv_dir="workspace/results/csv",
)
```

This keeps file naming consistent while letting each project choose
where artifacts live.
