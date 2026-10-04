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

## Editor workspace ownership and references

The dashboard's default draft collection is `<data>/drafts`. Use `--drafts /absolute/path/to/existing-drafts` to keep an established collection explicitly; changing `--data` no longer silently shares a source-relative collection. `launch_mac.py` also forwards `--drafts`. No live drafts are moved automatically.

For a reversible migration, stop the local dashboard, run `python draft_workspace.py ORIGINAL NEW_DESTINATION`, inspect the hash-verified copy report, then launch with `--drafts NEW_DESTINATION`. The destination must not exist. Keep ORIGINAL. Rollback is relaunching with the original `--drafts` path; do not restore an older project database. Do not point independently edited workspaces at one shared collection unintentionally.

New surface reference uploads retain original PNG/JPEG/WebP bytes in the owning draft's `references/` folder, named by SHA-256. Draft JSON carries asset identity, original/display dimensions and an explicitly marked UI thumbnail. Generation preparation verifies and copies the original bytes; legacy embedded previews remain marked preview-only. Portable project exports include original references and source-plan files. Missing or changed original bytes block preparation rather than silently substituting a thumbnail.

Use this plan is an explicit, revision-checked linking transaction. It can create a new project or add a floor to an explicitly selected existing project, retaining earlier plans/history. A new project starts paused with zero image/video/reference allowances. Linking creates an unconfirmed floor workspace extent, not certified room boundaries. Review and define rooms before generation. The linked manual document is authoritative; the old furnishing canvas links back to the floor-plan editor for architectural edits rather than overwriting junction/opening/surface data through its older SVG schema.

The initial fillet supports a two-wall right-angle L junction with matching physical properties. Radius is measured to the wall reference line. It trims tangents and creates shared editable geometry using at most 5-degree arc chords in both 2D and 3D. It rejects branches, acute/obtuse corners, insufficient length, and openings in the trimmed span. Move a complete merged chain rigidly; undo the fillet before altering its radius/tangency/properties. It is not a general parametric curve editor.

For non-inference browser checks, create a disposable data directory and start `make_server(..., start_worker=False)` without remote pairing. Never use production generation as a UI smoke test. Test save races through delayed responses and stale edits in independent tabs. Preserve the genuine generation phase, approval and staleness checks.

## Appearance

Dark is the default for new browser profiles. A Dark / Light switch is available at the bottom left of both workspaces; the former settings popup has been removed. Previously saved System preferences remain supported. The explicit choice is stored under `pixeloid.appearance` in localStorage for that dashboard origin; it never touches a project, scene revision or generation input. A parser-blocking `appearance.js` runs before styles/body, with a dark HTML fallback; System listens to device changes. Storage failure falls back to a usable session choice and reports that persistence is unavailable.

`appearance.css` owns interface tokens, status colours and monochrome application icons. Never put colour filters on uploaded media, SVG scene/material content, their ancestors or the document. The source drawing retains a white paper rectangle below its existing opacity/rotation overlay. Scene colours, guides used as generation inputs, camera rendering and original asset bytes do not depend on UI appearance. Use both themes when checking new tools and native controls. `node tests/test_appearance.cjs` covers synchronous defaults, stored/System preferences, storage restrictions, cross-tab changes, boot ordering and text contrast.

Code-only review tests need the normal dependencies, including Node and sharp: set `PIXELOID_NODE` to the installed Node executable and `NODE_PATH` to the dependency directory when they are not on the normal search paths. Run JavaScript suites from the source root. Do not bundle environments, bytecode, caches or private fixtures into a review ZIP.
