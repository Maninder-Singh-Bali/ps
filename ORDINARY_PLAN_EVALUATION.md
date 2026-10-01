# Ordinary furnished-plan evaluation — 1 October 2026

## Outcome

**Failed acceptance.** The dashboard has not demonstrated upload → useful detection → corrected furnished 3D → save/reopen for an ordinary real plan. The automatic result is saved and reopened, but remains partial and unverified. No geometry was manually repaired or approved in this trial. Do not call this a completed reconstruction, or extend any conclusion to curved hand-drawn plans. Plan 16 remains a separate difficult regression case with its original baseline preserved.

The tested drawing is the complete left-hand plan on supplied sheet 4: a monochrome residential plan with dining/kitchen/living space, bedrooms, bathrooms, laundry, garage, stairs and a patio. The façade, footer and right-hand plan were excluded in dashboard crop review. This is a supplied real example, not a synthetic control or training input. It was seen in the earlier isolated segmentation screening, so it is not an unseen holdout for that candidate.

## Reference and scoring

The reference covers the entire approved plan panel, not selected favourable regions: 48 wall spans, 12 door-system openings, eight windows/glazing spans, two open transitions, 38 visible furniture/fixture instances and 11 room/open-space zones. The reference was specified and checked by the assistant against the original pixels, including a second enlarged inspection to correct small opening positions before scoring. It is **not independently human-validated ground truth**. Small strokes, low-resolution symbols and opening endpoints have approximately 2–3 pixel uncertainty. Ambiguous cabinet/appliance identities need independent review. All reference geometry, annotation code, source images and overlays remain private and separate from the detector and saved project geometry.

Wall scores rasterize proposed paths with their inferred thickness, excluding a two-pixel reference boundary band. They measure both placement and thickness, not just centerline recall. Furniture matches require the same coarse class family and box IoU ≥ 0.25; for example dining/coffee tables share a family, so this does not certify the exact asset subtype. Door/window recognition uses the correct class, centroid within ten pixels of the reference span and a bound on predicted box size; matches are one-to-one and duplicate predictions count as extras. This is approximate recognition/localization, **not valid wall-hosted opening geometry**. The opening matching rule was clarified during scoring to avoid comparing door-swing boxes unfairly with thin reference spans. Reference geometry was not tuned to predictions. These are provisional diagnostic measurements, not a production accuracy claim.

## Untouched automatic output

| Measure | Result |
|---|---:|
| Wall precision / recall / IoU | 96.0% / 51.5% / 50.4% |
| Wall true / false / missed scored pixels | 2,578 / 107 / 2,430 |
| Architectural proposals | 13 wall paths; 19 uncertain stretches; zero typed openings |
| Door recognition | 5 of 12 matched; 7 missed; 44 extra predictions |
| Window recognition | 2 of 8 matched; 6 missed; 86 extra predictions |
| Furniture/fixture recognition | 20 of 38 matched; 18 missed; 39 extra predictions |
| Remaining unclassified predictions | 16 |
| Visual report | 228 estimates; 175 review issues |
| Coverage after continuation | No pending/failed regions; 3 saturated regions; exhausted, incomplete |

The best connected-space polygon overlap with each reference zone ranges from 0.009 to 0.280; none reaches 0.5 IoU. The ten OCR-derived section boxes are label-location suggestions, not reviewed room polygons. Those boxes were not treated as walls or slab geometry.

Original-image overlays show the exterior is partly useful, but thin internal partitions are missed. Some amber exterior contours follow the crop perimeter and must never be accepted as architectural walls. Furniture/annotation strokes are repeatedly called windows or doors; duplicate estimates greatly inflate the review burden. Furniture recognition misses enough visible instances that the requested scene cannot be populated reliably. No hidden furniture, ceiling lighting, upper storey or courtyard void was added. Default 3.0 m wall height and 1.6764 m human height remain assumptions, not horizontal calibration.

## Timings and interventions

Hardware remains RTX A4000 (15,352 MiB reported), Ryzen 9 5950X and 63.91 GiB RAM. Existing local Qwen3-VL 8B Instruct via Ollama was used without prompt, weight or detector-rule changes. CPU raster reconstruction used the installed SciPy runtime. No additional model or library was downloaded, and no training occurred.

- Upload action start to first saved raster draft: **45.112 s**, including source review. First raster job: **2.764 s**; final extraction itself: **0.612 s**. Preparation produced ten section suggestions automatically.
- Whole-plan visual processing: **328.11 s + 93.33 s = 421.44 s** across the bounded first run and cached continuation. Corresponding job wall times: **338.388 s + 95.333 s = 433.721 s**. The initial run hit its call limit; continuation exhausted the remaining regions with three saturated regions still unresolved.
- Additional work caused by the live lifecycle test: **42.36 s** model processing discarded after crop undo. An incorrect selected-room resume cost **21.70 s** before the bug was diagnosed and fixed. These costs are not hidden in the successful-scope timing.
- Upload start to final exhausted whole-plan report: **760.368 s** (12 min 40 s), including inspection, reference preparation, testing and debugging. This is **not** import-to-completed-furnished-model time.
- Manual project interventions were: approve only the left plan crop (remove right crop, check, save: **0.812 s**); undo crop approval while inference ran (**0.291 s**); reapprove the identical left crop at a new revision (**0.814 s**); click Resume (**0.326 s**, exposed the bug); initiate whole-plan cache recovery after fixing it (**0.278 s**). Upload interaction took **8.731 s**, including repeating the chooser invocation. These short measurements cover instrumented browser actions, not source-inspection time or human hands-on labour.
- **Geometry corrections: zero. Corrected furnished 3D completion time: unavailable. Human correction time: not measured.** No blanket approval or reference-geometry injection was used to manufacture a passing result. Saved/reopened evidence is the failed automatic project, not a corrected furnished model.

The private intervention log also records project creation, reload and verification. An initial new-project dialog was interrupted by page loading and reopened; the first upload chooser was invoked again with a captured chooser event. These are UI/test overhead, not detection corrections.

## Controlled deployment and blocking fix

Only the isolated evaluation dashboard was restarted. Its database was backed up first; the pre-existing evaluation projects and assets remained identical. The original Studio processes and projects were not restarted or rewritten. The segmentation candidate remains isolated and unregistered as a dashboard capability.

Live checks verified that approved crops resume raster reconstruction, preparation and semantic analysis automatically. Undo during inference cancels the old scope; its eventual completion is discarded. Reapproval creates one new job per stage with a new scope revision. The final exhausted result shows a disabled Detector exhausted control and survives reload. Eleven source-scope integration tests also pass, including excluded-reader pixels, crop transforms, stale completion and rollback.

This trial uncovered an additional blocker: the Review page's Resume action used the currently selected preview room, replacing a whole-plan report with a small room report. The fix makes new analysis on this page whole-plan and has the server recover the original analysis's section scope when resuming. The server rejects resume if the original job scope cannot be recovered. A regression proves both whole-plan and explicitly selected-section resumes ignore an unrelated preview selection. The cache remained valid because detector inputs, prompts and model code were unchanged. The broad automatic reports before/after the defect are preserved privately. The generic 3D heading no longer calls an empty draft furnished.

The isolated launcher now also points at the already installed Node/Sharp drawing runtime. This changes only its process environment; no runtime was installed or changed. After an idle, backed-up restart, the saved project reopened with the same automatic geometry and an exhausted detector. The original Studio processes remained running.

## Verification at this checkpoint

- `python run_tests.py`: 337 discovered, 333 passed, four SciPy-dependent pixel tests skipped in the lightweight application runtime; 34.476 s.
- `python run_tests.py test_raster_pixels.py` with the existing SciPy runtime: all four passed, 0.139 s. Together these cover all 337 distinct Python tests.
- Run every `tests/test_*.cjs` with the installed Node runtime: all 21 JavaScript suites passed. `node --check static/structure-check.js` passed.
- Source-scope integration: 11 tests passed. Structure API: seven tests passed, including resume retaining its original section scope.
- The first full test invocation had five export failures because the test environment pointed `NODE_PATH` at the wrong directory. Correcting it to the installed Node runtime's `node_modules` resolved them; no product fix was made to conceal that environment failure. Set `PIXELOID_NODE` and `NODE_PATH` when testing a source checkout against an external bundled runtime.
- Private preservation checks compare all pre-existing evaluation projects/assets with the pre-restart backup and verify the three Plan 16 automatic baseline hashes. All matched. No private evidence is part of the public source snapshot.

## Required next approach, before downloads or training

The evidence supports three concrete needs: architecture segmentation that preserves thin interior strokes without classifying furniture as walls; explicit door/window instances and host-wall/topology reasoning; and furniture-instance recognition with duplicate suppression and reliable coordinates. A room label box cannot substitute for boundary reconstruction. More prompt wording or more passes of this exhausted reader would not establish those capabilities.

Before proposing another download, verify that its published preprocessing and weights support **raw furnished raster images**, then test full-plan wall/opening/instance accuracy on independently reviewed examples. The isolated candidate's earlier performance does not justify integration. If no suitable licensed weights exist, independently reviewed, suitably licensed masks/instances and additional model development are required. Private evaluation drawings remain excluded from training. Commercial deployment and training are not authorized.

## Publication

GitHub write access still returned HTTP 403 (Resource not accessible by integration). Commit `3959c6dd6f0c980cf1d652ab27f4b194fe10b9c5` remains local on `dashboard-review`, not pushed. Its clean source ZIP contains 212 committed files, verified against Git contents apart from checkout line endings, and includes the earlier handoff and segmentation summary. A follow-up source ZIP also includes this report and the tested resume fix. Neither ZIP contains private plans, annotations, generated media, databases, credentials or model weights.
