# Development and validation

Normal users operate Upload, Review & 3D, Images & Video and Setup in the dashboard. The commands below are developer checks, not user workflow steps.

## Isolation

The original local checkpoint is `01b123d` on branch `improvements`. This publication is a fresh source-only root, with no private local history as parents. Its temporary projects are under `validation-artifacts/review-data`. `run_review.py` launches that database on port 8789; the normal launcher/server still uses the normal application database. Do not point the review launcher at the active Studio database.

## Checks

Run `python -m unittest discover -s tests -v` with the application's local Python dependencies available. Run `tests/test_raster_pixels.py` using a Python runtime with SciPy, NumPy and Pillow. Run `tests/test_*.cjs` using the bundled Node runtime. Some other `.cjs` files are fixture exporters and emit large JSON; they are not test suites.

`review_fixtures.py` builds an explicitly synthetic curve/void fixture. It must never be represented as automatically recovered geometry from the curved residence. Private source evidence and extraction artifacts were used locally and are deliberately excluded from this public snapshot. Public tests use independently constructed synthetic fixtures.

## Scene and rollback

Existing editable plan, drawing, room and furniture records remain authoritative. The scene document is an additive projection, not a destructive database migration. Source and element IDs survive export. `scene_document.migrate` adds metadata without changing original fields; `rollback` removes that addition. Tests cover round trips and preservation of manual corrections.

Raster corrections retain original paths, revision guards, source hashes and bounded undo/redo snapshots. A concurrent rescan saves suggestions separately if geometry changed during processing. Geometry and correction changes invalidate generation fingerprints and approvals. Restoring the baseline code requires a separate checkout plus the matching backed-up database; do not run older code over new work without a backup.

## Local services and privacy

Dashboard-owned renderer launches disable API nodes, custom nodes and automatic browser launch, and set offline Hugging Face/Transformers variables. Existing shared renderer processes are reused, not killed or reconfigured. An existing service's extensions/network policy are outside this launcher's control; core Studio graphs use only checked local nodes. No project data is sent to a cloud inference/conversion service.

Downloads are separate explicit-consent jobs with fixed URL, byte count, licence and SHA256. They preserve partial files, verify before installation and refuse to overwrite an installed model. No real model download was performed during validation.

## Accuracy evaluation dependency

The supplied curved residence is development evidence, not a held-out accuracy benchmark. Create reviewed original-resolution masks for walls, glazing, door leaves/swings, stairs, furniture, text/dimensions and unknown pixels; add centreline/contour geometry, thickness intervals, opening hosts and room topology. Preserve ambiguous/open-plan regions as such. Split by building/source, not adjacent crops, before training and evaluation.

Required held-out metrics include wall-mask precision/recall, boundary distance, junction correctness, opening-host accuracy, furniture-versus-wall confusion, room topology and calibrated uncertainty. Until annotated truth exists, these scores are unknown. Candidate counts and successful job completion are not detection accuracy. A locally runnable trained architecture segmentation component and a reviewed dataset remain dependencies for reliable automatic reconstruction.
