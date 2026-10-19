# Saving results and output names

## Explicit paths

The plotting API displays figures by default; it writes files only when an
explicit path or a legacy save flag is supplied. Prefer `plot_path` / `csv_path`:

```python
from pathlib import Path
import priorityx as px

plot_dir = Path("workspace/plots")
fig = px.plot_priority_matrix(
    results,
    entity_name="Service",
    plot_path=plot_dir / "matrix.png",
    csv_path=Path("workspace/tables/matrix.csv"),
)
```

Each path enables that output and takes precedence over its corresponding legacy
save flag, directory and filename. Parent directories are created. Supplying a
legacy directory or filename alone does **not** enable saving. `close_fig=True`
closes a figure after rendering; it is independent of saving.

The original plot helpers write PNG image content, including when an explicit
path has a different suffix. Use a `.png` path with those helpers. For another
Matplotlib-supported format, omit `plot_path` and call `fig.savefig("matrix.svg")`
on the returned figure. AutoViz's separate print renderer supports PNG and SVG;
see [exports](app.md#exports-and-offline-operation).

## Save full analytical tables

Keep complete analysis outputs separately from plot-selected exports:

```python
matrix.to_csv("priority_matrix.csv", index=False)
movement.to_csv("movement.csv", index=False)
transitions.to_csv("transitions.csv", index=False)
```

Use the actual variable name for your fitted matrix (`results` in the example
above). DataFrame `to_csv()` needs its parent directory to exist. The plotting
functions handle their own output directories.

| Export | Contents |
|---|---|
| Matrix plot `csv_path` | Core matrix columns plus explicitly mapped X/Y columns; other enrichment columns are omitted |
| Timeline plot `csv_path` | Filtered/selected displayed transitions, with display helper columns |
| Trajectory plot `csv_path` | Selected entities and retained path periods, after plot filters |
| Direct `movement.to_csv()` | Full movement table supplied by analysis |

Do not overwrite the full movement CSV with a trajectory plot's selected subset.
AutoViz needs the [saved-result schema](saved-results.md#required-columns), full
movement history for event classes, and explicit source/coverage metadata.
If extraction returns an empty transition table without headers, assign the
required empty schema as shown in the [quickstart](quickstart.md#save-results-for-autoviz).

## Legacy automatic names

The following applies only when `save_plot=True` / `save_csv=True` is used without
an explicit output path. Defaults are `results/plot` and `results/csv`, relative
to the current working directory. The workstation's current date supplies the
filename date; it is not the data coverage date.

| Helper | PNG prefix | CSV prefix |
|---|---|---|
| `plot_priority_matrix()` | `priority_matrix` | `priority_matrix` |
| `plot_transition_timeline()` | `transition_timeline` | `transitions` |
| `plot_entity_trajectories()` | `trajectories` | `trajectories` |

Names use `<prefix>-<entity_slug>-<cadence>-<YYYYMMDD>.<extension>`.
Timeline/trajectory `entity_slug` is `entity_name.lower().replace(" ", "_")`.
The original matrix helper uses `entity_name.lower()` and keeps spaces.
Cadence suffixes are
Q (Quarterly), M (Monthly), S (Semiannual) and Y (Yearly). The cadence argument
controls filename suffixes; it does not resample supplied tables.

```text
results/plot/transition_timeline-service-Q-20251018.png
results/csv/transitions-service-Q-20251018.csv
results/csv/trajectories-service-M-20251018.csv
```

## CSV helpers and movement reuse

`priorityx.utils.helpers.save_dataframe_to_csv()` saves the supplied table using
the same naming convention. `generate_output_path()` constructs that path and
creates the directory; it returns a relative path when `output_dir` is relative.
These helpers' `output_dir` arguments remain supported. An optional `key` replaces
the date with a 16-character lowercase hexadecimal fingerprint; keyed saves use
an atomic replacement. `latest_artifact_csv()` without a key searches date-only
names; with a key, it finds only that exact request and never falls back to a
different key or dated file.

`load_or_track_movement()` uses keyed filenames:

```text
movement-service-Q-a8f3c2d194e76b02.csv
```

The key reflects the complete supplied DataFrame (including index, column names,
dtypes and order), identity/date mappings, normalized schedule, thresholds,
priors, inactivity window, effective seed and package/cache version. These are
illustrative keys, not data coverage dates. Apply data filters before calling;
changes to unused columns also invalidate the cache conservatively.

| Request | Behavior |
|---|---|
| Same data and settings | Reuse the exact CSV; no fitting or rewriting |
| Changed data or settings | Compute a separate keyed file; preserve other results |
| `use_cache=False` | Recompute and atomically replace only the matching file |
| Only old date-only CSVs exist | Leave them untouched and compute a keyed result |
| Matching keyed CSV is unreadable | Raise an error; do not silently refit |

Failed fitting or saving leaves previous output intact. No manifest, timestamp
or run counter is added to keyed cache names. A readable file's manually edited
values are not detected; these are request fingerprints, not output checksums.
The first call after upgrading can refit because old caches cannot establish
which inputs produced them.

For Monthly, the wrapper returns canonical `quarter` in memory and saves `month`
on disk. Cache reads never rewrite a header. This explicit analysis/cache helper
has disk effects; opening results in AutoViz does not invoke it.
