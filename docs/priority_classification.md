# Quadrants, transition risks and event classes

PriorityX exposes three related concepts. Keep them separate when interpreting
charts or filtering saved results:

| Concept | Produced by | Values |
|---|---|---|
| Score quadrant | Fitting / movement tracking | Q1–Q4, from score signs |
| Saved transition risk | `extract_transitions()` | `critical`, `high`, `medium`, `low`, `stable` |
| Displayed event class | Timeline / AutoViz preparation using movement | 1 Crisis, 2 Investigate, 3 Monitor, 4 Low |

A red Q1 point in a matrix and a red Crisis event use separate rules. Quadrants
are score positions, not calendar quarters, ranks or verified current status.
See [methodology](methodology.md) for score scales and inclusion filters.

## Saved transition risks

For cross-quadrant changes, extraction uses these mappings:

| Transition | Saved `risk_level` |
|---|---|
| Q2/Q3/Q4 → Q1 | `critical` |
| Q3/Q4 → Q2 | `high` |
| Q4 → Q3 | `medium` |
| Q1 → Q2, Q1 → Q4, Q2 → Q3 | `low` |
| Other cross-quadrant changes | `stable` |

The default `focus_risk_increasing=True` removes cross-quadrant `low` and `stable`
rows. Pass `False` to retain them. When the quadrant is unchanged, extraction
checks a positive `y_delta > 1.0` first (`*Y`, `critical`), then positive
`x_delta > 1.0` (`*X`, `high`). If both exceed 1.0, that extraction branch records
`*Y` because Y has precedence. It does not generate every possible display spike.

Filter saved risks with their actual column:

```python
critical_transitions = transitions[transitions["risk_level"] == "critical"]
```

These rows are not necessarily the same as Crisis events after display preparation.

## Displayed event classes

When full movement history and cumulative counts are available, the renderer
compares an event's score position/count with its preceding saved movement row.
The first matching rule wins:

| Class | Rule |
|---|---|
| **1 Crisis** | `abs(delta_x) > 0.40` or `abs(delta_y) > 0.40`, or count growth `> 500%` with a count increase `> 50` |
| **2 Investigate** | Either absolute score delta `> 0.15`; otherwise a destination exactly `Q1` with both coordinates outside the boundary band; otherwise growth `> 100%` with count increase `>= 5` |
| **3 Monitor** | Either coordinate has absolute value `<= 0.10`, or the destination is exactly `Q1`, after the earlier rules fail |
| **4 Low** | No earlier rule matches |

The comparisons are strict where shown: exactly 0.40 is not a Crisis score
trigger. Extreme negative score moves also satisfy the absolute-delta rule.
Counts are changes in cumulative event rows, not a percentage change in the
single-period count; a zero preceding cumulative count gives a zero percentage.
A saved destination suffix is passed through, so `Q1*Y` is not the exact `Q1`
string used by the destination-specific branches.

The display falls back to Investigate when the matching current row, preceding
history or cumulative counts are unavailable. Preserve history and its original
chronological row order before display filtering; do not send a YTD-only movement
extract for class calculation. Plotting does not add a `priority` column to the
caller's transitions. AutoViz's prepared events expose the class separately.

## Spike suffixes

During display classification, the absolute score-spike tests above give `*X`,
`*Y` or `*XY`. A count-only Crisis uses the compatibility `*Y` marker. If a saved
`to_quadrant` already contains a suffix, the display preserves it rather than
replacing it. Therefore suffixes can originate from extraction or rendering;
the extraction and display thresholds are not interchangeable.

In compact notation, `3→②*XY` reads source Q3 → destination Q2, with both-axis
spike indication. Marker date/coordinates remain at the event. Color identifies
the displayed event class independently of the destination digit.

## Threshold interpretation

These are fixed operational heuristics in the implementation. The repository does
not establish a percentile, sigma equivalence, calibrated detection accuracy or
universal response action for them. Count-model log effects and standardized
continuous-metric effects use different scales. Review historical performance
and false-positive tolerance for your own data and workflow.

The display classifier is `priorityx.tracking.transitions.classify_priority`.
The driver-analysis helper `priorityx.tracking.drivers.classify_priority` uses
`Critical` for numeric class 1 and a `count_delta` argument; timeline displays use
`Crisis`. These labels are algorithmic classifications, not outcome verification.
