# Local saved-results workspace

The development workspace opens validated saved results without fitting models.
It uses Plotly.js for linked quadrant matrices, transition timelines and
trajectories. The existing Matplotlib plotting API and its defaults are unchanged.

The workspace requires Python 3.12 or later. The source checkout defaults to
Python 3.12; CI is configured for Python 3.12, 3.13 and 3.14.

```sh
priorityx app --bundle results.json
# Equivalent when running from a source checkout:
python -m priorityx app --bundle results.json
```

Omit `--bundle` to open an empty workspace. `--port 0` chooses a free port;
`--port 8765` chooses a particular port. `--no-browser` prints the address without
opening it. The service binds to `127.0.0.1` and keeps one bundle in memory.
It serves application assets only. It does not expose a filesystem browser,
write analytical outputs automatically, or provide remote hosting.

## Open and inspect

Use **Open results → Open result bundle** for a version 1
[result bundle](saved-results.md), or **Open results → Import CSV files** for
explicitly assigned matrix, movement and transition roles. Import opens a dialog;
closing it preserves the entered fields. Supply type, cadence, coverage and source metadata. CSV import validates
required columns, duplicate headers, exact row widths and numeric values.
Additional columns remain caller metadata; source-specific mapping happens in
the caller's adapter. A failed import leaves the current workspace intact.

Type labels come from the bundle. Quarterly opens when available; a bundle with
only Monthly results opens Monthly. The timeline shows January/Q1 through the
latest saved period in the snapshot year, including blank periods. Preparation
uses full movement history before display filtering. Missing tables or selected
entities without fitted points/paths are identified beside the affected chart.

Selecting an entity links all charts. Type changes clear selection and reset the
view; cadence changes retain the entity when it exists in the other cadence.
Chart navigation and zoom do not make service requests or fit models. Exact
matrix, event and trajectory values are available in **View data**, with Matrix,
Timeline and Trajectories tabs. Each chart's **Data** link opens its matching tab.
Arrow keys, Home and End move between tabs. Timeline period headings remain
visible during vertical scrolling.

Without an explicit saved trajectory selection, the workspace shows up to three
entities with the largest total absolute trend changes over the displayed path
window. Both rises and falls count. The default window is eight quarters or
12 months; equal scores use entity identifiers as a deterministic tie-breaker.
An explicit saved list keeps its order. **Details** explains which selection
mode is active. Selecting an entity shows its individual path; clearing selection
returns to the default group. Named keys and endpoint letters identify the shown
paths; line patterns distinguish paths that share a quadrant color. The trajectory
table opens on the shown paths; **Show → All saved entities** includes all saved
paths within the same period window. See [the saved-result selection contract](saved-results.md).

## Layout and continuity

**Layout** opens a settings dialog and controls equal panel dimensions. Closing
the dialog retains unapplied edits; a visible reminder keeps them discoverable.
The timeline fits the panel width
automatically: names wrap, period labels shorten when needed and crowded event
groups use separate lanes within their entity row. Every YTD period and event
remains available without horizontal timeline scrolling. Exact values remain
in **View data → Timeline** below the charts. Apply layout
before exporting changed settings. Measured placement wraps matrix labels and
separates trajectory endpoint labels without changing saved coordinates.
Unresolved conflicts remain visible and are included in the layout report.

**Reset view** restores chart ranges and timeline position.
**Reset settings** restores the complete display defaults. Browser storage retains
selection, actual axis ranges, scroll positions, data tabs, trajectory table scope
and disclosures for each bundle. Menus and dialogs close on reload or export;
older version 1 settings with separate table folds still open the corresponding
data tab. **Save settings** and **Load settings**, inside **Layout**, provide an explicit portable round trip;
settings for another bundle or unsupported schema are rejected.

## Exports and offline operation

**Export → Save offline HTML** embeds the pinned Plotly basic 4.1.2 asset, result bundle, prepared
views and settings. It reopens without a server or network, including type/cadence
controls, linked selection, zoom, data tables and settings save/load. The file
contains full saved history beyond the visible YTD window. Matrix SVG export also
works offline. Treat exported data with the same care as the source bundle.

The **Export** menu also provides matrix SVG and print PNG/SVG. Print exports
require the local Python service. They use the same chart
populations, saved scores, event classes/suffixes and trajectory window, with a
separate print profile; browser zoom does not crop the print population.
Automatic sizing follows bounded, deterministic dimension candidates. Manual
dimensions win. Minimum chart text is 12 pt. Remaining clipping/overlaps are
reported, with every analytical mark retained. Exports have a 30-second render
deadline, and concurrent print requests are rejected with a retry instruction.
Downloads from an older view are discarded if the view changes during rendering.

The new opt-in renderer is also available directly:

```python
from priorityx.results import ResultBundle
from priorityx.views import prepare_bundle, resolve_settings
from priorityx.viz.export import render_static

prepared = prepare_bundle(ResultBundle.load("results.json"))
settings = resolve_settings(None, prepared)
dataset = next(d for d in prepared["datasets"]
               if d["entity_type"] == settings.entity_type
               and d["cadence"] == settings.cadence)
fig, report = render_static(dataset, settings, "timeline")
fig.savefig("timeline.png", dpi=settings.dpi)
print(report.to_dict())
```

## Build boundary and qualification

Application HTML/CSS/JavaScript, Plotly and its MIT license live inside the Python
package. `build_html()` reads those assets directly; there is no Node runtime,
CDN fetch or dependency on development prototypes. Build distributions with
`uv build`; no additional Python runtime dependencies are required.

Cross-platform Python code is provided for Mac and Windows. Platform fonts,
physical touch and Safari behavior require separate qualification.
Future private hosting needs its own access and deployment design; the local
launcher deliberately does not expose a remote bind option.
