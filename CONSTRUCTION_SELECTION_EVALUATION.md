# Apartment construction selection — local evaluation

1 October 2026. Private dimensioned typical-floor vector PDF; source, client identifiers, overlays, project database and generated geometry remain local and are not included here.

## Outcome

A selected apartment is saved as an editable, manually corrected draft with 2.50 m walls, twelve room/outdoor zones and nine source-visible sanitary/kitchen fixture proxies. The original sheet and coordinate system are preserved. The user supplied wall height; scale was calibrated manually using a printed 4.105 m dimension. Opening head/sill heights, leaf poses and fixture dimensions are still assumptions. This is **not** an automatic architectural-reconstruction acceptance pass or a verified construction model.

## Automatic baseline versus corrections

- Native extraction retained 14,288 PDF drawing paths, represented by 14,434 unclassified detail elements in the editor. It supplied no typed walls, doors or windows suitable for automatic extrusion.
- Initial preparation proposed eighteen label-based section boxes on an unassigned floor. Those original proposals remain saved; they were not turned into walls or treated as reviewed room polygons.
- A semantic study automatically started after preparation and was cancelled during its second region. No predictions from that study were installed in this apartment draft. The exhausted raster research cases were not rerun.
- Manual work: one apartment polygon, one open-to-sky exclusion, 27 wall runs (including an adjoining-wall exclusion control), 13 door elements, 11 window elements, twelve zone polygons and nine library assets. Window classifications and door interpretations remain manual proposals.
- Four balcony zones were classified as outdoor. The kitchen boundary was adjusted. Seven apartment-outline corners were adjusted after cut warnings. A printed dimension was calibrated, wall height and site orientation were supplied, and all fixture centres/sizes were reviewed for mapped-feature overlap.
- Two mistaken insertions were undone: an accidental staircase asset and a toilet added to the wrong active room while the editor was busy. The draft contains neither erroneous addition. Bathroom and kitchen proxies were moved or proportionally resized to fit. Their exact product geometry is not established by the source.
- No beds, sofas, lighting or extra storey were invented. Any later furnishing absent from this drawing must be identified as proposed design.

## Scope and persistence verification

- The original source hash and image dimensions match the untouched import baseline.
- All twelve reviewed zone polygons have 100% coverage inside the final construction selection. No room or furniture boundary-cut warning remains.
- All seventeen generated floor faces lie wholly within the selected region, excluding the open-to-sky polygon. No neighbouring apartment floor is constructed.
- The adjoining source wall continues beyond the apartment. It is clipped at the chosen boundary, with the tiny shared-junction portion retained and full wall thickness preserved. Its continuation into the neighbour is excluded. The selection perimeter never becomes a generated wall.
- The corrected scene contains 72 wall/opening spans and nine fixture assets. All nine pass the existing mapped-wall/room placement checks; this does not certify walking clearances or missing source geometry.
- A controlled restart of the isolated evaluation service preserved an exactly equal saved scene. A subsequent final fixture save is checked through fresh-page reopening. Original Studio services and projects were not restarted or changed.
- Construction selection history retains earlier outlines; changing the selection does not delete drawing edits or furniture placements. Scene/control identities include the selection revision.

## Timing and review effort

Initial preparation completed in 23.73 seconds. A final shared-scene request took 2.88 seconds. The local session reached the final geometry audit 54.69 minutes after import, including implementation, diagnosis, correction, testing and restart; this is not inference time.

The detailed private log records 51 wall/opening interactions taking 163.68 seconds in aggregate and twelve polygon-creation interactions taking 21.31 seconds. These are automated pointer-operation timings, not measured human correction time. Fixture/correction timing is incomplete, and the total click count was not captured. No end-to-end human-effort benchmark is claimed. The scope of manual intervention is substantial; this run does not demonstrate useful automatic wall recognition.

## Source fixes and tests

- Added a saved construction-scope contract, rectangle/polygon/void editing, reviewed-boundary candidates, cut warnings, preview confirmation and reversible selection history.
- Applied scope to shared geometry, raster drafts, floor faces and complete rotated furniture footprints; unconfirmed selections cannot construct a draft.
- Kept dense unclassified vector artwork as a reference image in the furniture workspace while retaining typed editable features. Native edits or typed native geometry disable that simplification. Replaced repeated native-element searches with a lookup map.
- Reused the selection viewer across refreshes, rejected stale viewer responses, restored the approved floor when reopening, and made editor busy state visible to prevent silently applying actions during a section switch.
- Drawing-runtime diagnostics now use the same configured local runtime as the drawing exporter.
- Final screenshot review exposed an inline-view scale bug: excluded/unassigned floor placeholders could supply the building's base scale and elevation. Those placeholders are now removed before building and walk-coordinate calculations. A regression test proves they cannot change constructed geometry, heights or ceilings. Saved backend geometry was unaffected.

Validation: 354 Python tests exercised successfully across the existing base runtime and the existing SciPy runtime (four SciPy tests skipped by the base runtime then passed separately). All 23 JavaScript suites passed. `node --check` passed for the updated application and selection UI scripts. Tests include selection clipping, full boundary thickness, voids, rotated furniture, stale previews, saved edits, undo, floor isolation, scope-sensitive control snapshots, dense-source preservation and selected-floor reopening. These use sanitized fixtures.

Run Python suites with `python run_tests.py`; run each `tests/test_*.cjs` with Node. Pixel-only tests require the documented optional SciPy dependencies. No new model or runtime was downloaded for this selection task.

## Remaining limitations and review priorities

- The native PDF paths still lack architectural semantics. Producing this draft required tracing/reclassification and reviewed room outlines; no automatic apartment-boundary detection is claimed.
- Wall thickness was estimated from source strokes. The local dimension calibration uses manually placed endpoints. Door handedness, opening interpretation, head/sill heights and some boundary transitions need a second architectural review.
- Balcony railings, cupboard/column detail and ambiguous entrance geometry are incomplete. Some balcony/ancillary areas are included in the selected slab but lack separate room polygons. Open edges remain open rather than receiving invented walls.
- Exact cabinetry lengths and sanitary fixture shapes are not reproduced by the library proxies. Their placements pass current mapped-feature checks, but ergonomic or construction accuracy is not certified.
- Construction scope limits output geometry; analysis can still read surrounding source context. Review the clipping tolerance at boundary faces, concave/multiple selections, inner void boundary walls and stale asynchronous UI responses on further samples.
- Incomplete private timing means this run cannot substantiate a hands-on productivity claim. A future acceptance run needs uninterrupted action logging and independent reference annotations.

Private evidence is retained beside the local evaluation workspace. No source drawing, client report, precise site location, model weight or generated media belongs in the public snapshot.

Publication recheck: the base suite passed 350 tests and skipped four optional SciPy tests in 36.004 s; the four pixel tests then passed in 0.149 s in the existing SciPy runtime. All 23 JavaScript suites passed again, including the excluded-floor viewer regression. An initial run without the configured Node/Sharp environment failed five drawing-export checks; rerunning with the existing `PIXELOID_NODE` and `NODE_PATH` resolved those environment failures. Set those to the installed Node executable and its dependency folder when using an isolated Python runtime.
