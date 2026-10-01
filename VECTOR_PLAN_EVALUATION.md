# Real dimensioned vector-PDF dashboard evaluation

Date: 1 October 2026. Source baseline: `3003de74a37311e84974a9721f40115fb9cfa91c`.

## Outcome

A real first-floor vector PDF was uploaded, manually classified/corrected, furnished with proposed assets, saved and reopened entirely through the isolated dashboard. Saved and reopened scene data are exactly equal. **This is a manually assisted editable 3D draft, not a successful automatic semantic reconstruction or a verified complete architectural model.** Raster detector acceptance remains failed; no inference about curved hand-drawn plans or DWG support follows from this case.

Source: the Backcountry 2D floor-plan sample from [Twindo's sample page](https://sampledata.twindo.com/twindo-sample-files). The two-page PDF was retained locally for evaluation only; no redistribution licence was established. Only the complete first-floor sheet was reconstructed. The second page remains unreviewed. No floor was inferred from the staircase. The drawing contains architectural fixtures but no loose furniture; every added furniture asset is named **Proposed**.

## Automatic baseline, before correction

- Native extraction retained 2,474 paths on page one, along with source-path identities. It extracted **zero typed walls, zero openings, zero room boundaries and zero furniture assets**. The original automatic database and screenshot were preserved separately before correction.
- CPU preparation ran for 6.347 seconds after 1.100 seconds of queue wait; first-page preparation finished approximately 9.54 seconds after upload began.
- Upload also automatically scheduled local visual reading. It was stopped in the dashboard. The first-page report recorded 59.6 seconds and eight low-confidence partial estimates, including a stair and repeated erroneous bathroom labels. None became model geometry. The second-page analysis was cancelled before processing. This was a new optional upload-triggered read, not a rerun of either exhausted raster benchmark.
- No detector precision/recall score is claimed from path counts. All semantic walls and openings in the final draft required explicit human-style review or placement.

## Manual reconstruction

1. Highlighted 42 matching, opaque filled native rectangles and reviewed them against the original before explicitly classifying them as walls/piers. Matching fill is only a selection aid. It does not automatically establish architectural meaning.
2. Replaced two misleading clipped rectangular fills with source-supported diagonal wall segments; endpoints and thickness were picked approximately in the dashboard. The other source shapes remain unclassified rather than becoming bounding-box walls.
3. Traced an 18-point floor perimeter. Calibrated against the printed 14 ft 4 in inside-face dimension. A separate printed 10 ft 8.5 in dimension agrees within approximately 0.4%, consistent with pointer-placement error. Resulting scale is about 0.01562 metres per drawing pixel.
4. Drew nine room/zone polygons: Northwest room, Washroom, South washroom, Northeast room, Northwest closet, Hall, Main open room, South room and East room. These are positional review labels, not automatically inferred room uses. Open zones do not create new enclosing walls.
5. Placed six source windows, ten door/opening elements and one multi-panel closet-opening proxy. Set their depths from host walls. Window positions and doorway gaps are source based; mechanism and vertical detail are not all reproduced.
6. Set the floor wall height to the printed 8 ft 5 in (2.5654 m). This is a measured source value for the principal height; applying it to the whole floor is an approximation. The 5.5 ft (1.6764 m) human reference remains a standard assumed reference, not a scale measurement.
7. Added seven proposed furniture assets: two double beds, a living sofa, coffee table, dining set with four chairs, desk and desk chair. They were named and positioned in the dashboard. No proposed lights were added. Furniture sizes are library presets using the calibrated scale, not dimensions measured from this unfurnished source.
8. Saved, restarted only the idle isolated evaluation service with a database backup, reloaded the dashboard and reopened the project. All nine zones and seven assets remained visible in synchronized 2D/3D.

Final scene: 59 rendered wall spans after opening cuts, six windows, ten door elements and one sliding-door proxy, plus seven furniture asset records. Wall-span count is an implementation count, not 59 independently surveyed walls. Footprint approximately 17.49 by 15.23 m; principal height 2.5654 m. About 15.29% of the floor area is outside assigned room polygons, including wall area and unassigned recesses; full room coverage is not claimed.

## Timing and intervention accounting

| Measurement | Actual result |
|---|---:|
| Upload start to saved furnished draft | 23 min 49.93 s |
| Upload start to verified reopening | 25 min 28.54 s |
| First native CPU preparation | 6.347 s |
| First CPU queue wait | 1.100 s |
| Cancelled/unused local visual read, reported elapsed | 59.6 s |
| First classification review through final save, wall-clock | 20 min 29.64 s |
| Recorded correction interaction intervals, overlaps merged | 6 min 8.79 s |
| Recorded all-operation interaction intervals, overlaps merged | 7 min 44.91 s |
| Correction log entries / all operation log entries | 42 / 48 |

These are agent-assisted dashboard timings, not a measured human usability study. The overall interval includes source inspection, two blocker fixes, controlled service restarts, test execution, tool latency and verification. Recorded interaction intervals are a **lower bound**: one bed-placement start time was not captured, and thinking/source-review gaps are not included. Entries group multiple clicks; they are not individual mouse-action counts. Overlapping room-save and desk/chair intervals are merged, not double-counted. The private intervention log retains coordinates and timestamps for every recorded correction group.

## Only demonstration blockers changed

- Added explicit review/classification of true opaque native rectangular path fills, preserving original path identity and restoring it when unclassified. Open, curved, irregular and transformed paths cannot be converted using their bounding boxes. No sample-name or coordinate rule was introduced. Source PDF clipping still requires manual review.
- Fixed shared-floor bounds to include the saved matching-floor perimeter, not merely room interior faces. This restored exterior walls and two windows previously clipped out of the scene. Bounds remain scoped to the matching plan and floor.
- Added five native-review regressions and an exterior-envelope/floor-isolation regression.

## Remaining failures and limits

- Native geometry import does not yet interpret this unlayered PDF's walls, room topology, symbols or dimensions automatically. Manual review dominates the useful result. A generic native-path topology/symbol interpretation stage, including PDF clipping and opening relationships, is the next recognition need; repeated vision prompts are not a demonstrated remedy.
- Bathroom fixtures and staircase treads/railings visible in the source were not reconstructed. There is no complete source-object inventory in 3D.
- Local lower ceilings and beams (including other printed heights) are not modeled. Printed door heads and individual window sill/head dimensions were not applied; opening heights remain illustrative defaults. The broad connecting door and multi-panel closet mechanism are simplified proxies.
- Two diagonal corrections have approximate endpoints/thickness. This is not construction-ready geometry or independently reviewed reference annotation.
- The 2D native redraw retains dimension/text outline clutter. Advanced wall/area correction still uses existing dashboard editors; this run does not prove a frictionless single-pane workflow.
- No second-floor reconstruction, raster-detector improvement, FLUX/LTX generation or DWG conversion was attempted.

## Verification and preservation

Saved/reopened geometry hash: `630e4ad9d11d10a7fae71749667f8ca83785e72643b9406686bccacf816ae47d`. Complete scene equality also passed (canonical sorted JSON SHA-256 `264b05168f015074a832e52997d9795cf41e5ef9ddb25fa0e707af10bf0b264d`). Original sample bytes and every pre-existing evaluation project record were unchanged. The original Studio services were not restarted or modified. Plan 16, the ordinary raster baseline and isolated segmentation research were left intact. No model download, training, cloud inference or candidate integration occurred.

Local evidence includes the untouched automatic import screenshot/database, highlighted source paths, corrected room overlay, saved and reopened furnished-model screenshots, per-action log and test logs. These and the source PDFs/CAD files remain outside Git.

## Actual test results and commands

- `python run_tests.py`: 343 discovered, 339 passed, four SciPy-dependent tests skipped in the primary runtime; 34.829 s.
- `python run_tests.py test_raster_pixels.py` in the already-installed SciPy runtime: all four skipped tests passed; 0.143 s. Thus all 343 Python tests were exercised across the two installed runtimes.
- All 21 `tests/test_*.cjs` suites passed using Node with the existing sharp dependency. These unit tests did not rerun the real raster analyses.
- Dashboard import, manual review, calibrated room tracing, furniture placement, save and fresh-service reopening were exercised against the real sample, not only mocked tests.

Use the setup and runtime environment documented in SOURCE_SETUP.md. Node must resolve sharp; PIXELOID_NODE and NODE_PATH can select an existing installation. Hardware remained the local RTX A4000 16 GB / 64 GB RAM Windows machine; the native geometry path uses CPU processing and did not require a new model.
