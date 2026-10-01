# Pixeloid Studio — external review handoff

Tested source checkpoint, 1 October 2026. Start here when reviewing this repository with ChatGPT or another code-review tool.

## Scope and publication boundary

This is the complete reviewable application source, UI, workflows and tests, not a runnable bundle containing models or client projects. It is a fresh Git root snapshot of the tested local checkpoint `01b123d`, with publication-specific sanitization. The private local commits are not ancestors of this branch. The original working installation, commits and client files were preserved unchanged.

Excluded: client floor plans and detections, screenshots, generated media, project databases, credentials, private configuration, machine-specific import scripts, model weights, bundled runtimes, caches and logs. Public fixtures are generated synthetic shapes or generic test data. One private-plan conflict regression was replaced with an independent synthetic fixture covering the same six conflict cases. No client geometry was copied into that fixture.

## Completed work

- Upload / Review & 3D / Images & Video navigation in the existing dashboard.
- Original-preserving image preparation; native PDF/DXF path, layer, entity and transform metadata; explicit unsupported-DWG messaging.
- Local original-pixel wall masks, skeleton paths, line/arc/spline fitting, uncertain exterior contours, opening candidates and connected-space proposals.
- Source overlays with focused point corrections, opening classification, saved revisions and undo/redo; synchronized partial 3D. Native geometry previews no longer wait for room recognition.
- Preserved curved architecture, polygon floors and voids where supported geometry exists; GLB and structured scene/provenance export.
- Checkpointed local semantic analysis, original/enhanced disagreement and conflicting-label review. Detection rectangles never become walls.
- Dashboard setup/readiness, installed-service startup, local-only endpoints, memory guards, serialized heavy jobs, cancellation, retry and ambiguous-submission recovery.
- Explicitly approved, resumable downloads with pinned size/hash/licence. Current catalogue covers one FLUX diffusion weight only.
- Existing furniture/material references, camera controls, local FLUX image generation, image approval, LTX video generation, playback and export retained.
- Scene fingerprints invalidate approvals after geometry changes. Design-light proxies are separate from observations; no detected lights does not prove no lighting exists.

## Current detection and 3D limitations

The raster tracer is deterministic SciPy/NumPy/Pillow processing, not trained architectural segmentation. It recovers supported strokes but can confuse thick furniture outlines with walls and miss thin glazing or doorways. Exterior classification, opening hosts, junctions and complete room topology remain provisional. Open-plan spaces are not forcibly enclosed. Connected free space is not automatically a confirmed room or slab.

A partial 3D preview is explicitly unverified. Raster-only drafts lack complete furnished-room assembly and a final geometry-clearance workflow. Specialist editors still exist under Advanced. Estimated scale and default heights must not be represented as measured dimensions. DWG has no validated compatible local adapter.

FLUX reference-latent conditioning is soft. Depth, normal, object-ID and edge guides are exported, but no validated geometry-control model enforces them. A local synthetic render test invented openings and failed architectural review. The image and derived video were rejected after a test-only LTX approval was removed. Attractive media and completed jobs do not establish reconstruction accuracy.

There is no annotated held-out accuracy benchmark. No precision/recall, wall error or room-IoU claim is made. Trained local architecture segmentation plus reviewed masks, curves, opening relationships and room topology are still needed. Automatic proposed-lighting layouts and separate-sheet registration are unfinished.

## Actual test results

The sanitized public copy was re-tested after replacing the private fixture and adding portable Node resolution:

| Test | Actual result |
| --- | --- |
| Python suite | 295 discovered in 44.608 s: 292 passed, 3 skipped because that runtime lacks SciPy |
| Those 3 pixel tests, installed SciPy runtime | 3 passed in 0.905 s; all 295 tests exercised across the two appropriate runtimes |
| JavaScript | All 19 `tests/test_*.cjs` suites passed |
| Final fixture sanitization | All 36 product/furniture tests passed in 2.265 s after replacing retailer references with generic examples |
| Earlier installed-app dashboard journey | DXF upload, native preview, original-byte preservation, GLB export, point correction/undo and opening defer/undo passed |
| Earlier local media execution | FLUX ~45 s; LTX 5-second clip ~481 s; playback and export passed at 1920×1080, 24 fps, 120 frames |
| Media fidelity | Failed architectural review; invented openings were recorded and outputs rejected |

The installed-app UI/media results predate publication sanitization. No fresh model render or cloud inference was required for publication. Private screenshots and logs are deliberately omitted. Test duration is machine-dependent; tests are not an accuracy benchmark.

### Publication checks

All 197 staged files were inspected with a local pattern scanner for credential formats, credential assignments, authenticated URLs, private filesystem paths, client identifiers and excluded file types. The public gazetteer was decompressed for inspection; the sole PNG is the UI logo and has no embedded metadata. The only retained credential-shaped strings are deliberately invalid dummy URLs in rejection tests. No sensitive-content findings remained. This is a pattern scan and manual review, not a guarantee of exhaustive secret detection.

Both original local commits were inspected and kept private. The publication branch starts with a single parentless commit; its reachable file contents are scanned again before pushing. Local test logs and audit manifests remain outside this repository.

### Test commands

After the developer dependencies in SOURCE_SETUP.md are installed, from the repository root:

```powershell
python -m unittest discover -s tests -v
Get-ChildItem tests -Filter 'test_*.cjs' | ForEach-Object {
  node $_.FullName
  if ($LASTEXITCODE -ne 0) { throw "Test failed: $($_.Name)" }
}
python -m unittest discover -s tests -p test_raster_pixels.py -v
```

Use the Python runtime with SciPy for the pixel tests. `PIXELOID_NODE` can select an existing Node executable; otherwise Node is resolved from the bundled path or PATH. Do not execute fixture-export `.cjs` files as test suites: they print large geometry JSON.

## Local startup and dependencies

See [SOURCE_SETUP.md](SOURCE_SETUP.md). The source checkout needs Python, Node/sharp and the libraries in `requirements.txt`. The local application was tested with Python 3.13.14 on Windows and an RTX A4000 with about 15 GB VRAM / 64 GB RAM. This does not certify other hardware.

The dashboard can start configured local ComfyUI and Ollama services and verifies their readiness. The fresh-machine installer is incomplete. Runtime paths belong in ignored `studio.local.json`; `studio.example.json` contains no credentials or machine-specific paths. Core inference must remain local; approved dependency downloads are distinct from project processing.

Missing from this repository by design: ComfyUI/PyTorch, Ollama and visual-reader weights, FLUX/LTX encoders and VAEs, optional Real-ESRGAN/Spandrel, all model binaries. Required filenames are listed in SOURCE_SETUP.md and the workflow templates. Missing capability must produce an actionable dashboard limitation, never cloud fallback.

## Specific areas needing external review

1. **Reconstruction correctness:** `raster_geometry.py`, `raster_reconstruction.py`, `drawing_scene.py`, `curve_geometry.py`. Review masks, curve tolerance, false furniture walls, opening host cuts, junction topology and uncertainty propagation. Propose measurable improvements and a concrete local segmentation/data dependency.
2. **Shared state and preservation:** `scene_document.py`, `scene_control.py`, `store.py`, `detection_review.py`, `plan_health.py`. Review stable identities, concurrent edits, cache invalidation, undo rollback, approval invalidation and migration compatibility. The scene document is an additive projection; multiple legacy editable records remain authoritative.
3. **Local job safety:** `engine.py`, `job_control.py`, `standalone.py`, `local_setup.py`, `component_setup.py`, `vision_study.py`. Check model residency, cancellation ownership, restart recovery, duplicate submissions, partial downloads, licence consent and memory limits. Headroom thresholds are not model-specific peak-memory predictions.
4. **Image fidelity:** `geometry_guidance.py`, `shared_floor.py`, `templates/flux.json`, `templates/ltx.json`. Recommend compatible local structural conditioning and verification, not repeated prompt changes as a geometry substitute.
5. **UI integration:** `static/structure-check.js`, `static/raster-review.js`, `static/plan-workspace.js`, `static/local-setup.js`. Reduce specialist-editor fragmentation, make incomplete rooms actionable, preserve view/selection and review accessibility/error states.
6. **Security and packaging:** `server.py`, `web_image.py`, `products.py`, download handling and setup. The server is loopback-only, not authenticated for public hosting. Do not expose it through a tunnel. Assess source installation reproducibility, licences and clean-repository exclusions.

Please separate verified defects from hypotheses, cite files/lines, preserve existing user corrections, and propose small testable changes. Do not infer that missing client examples, binaries or private history should be added to this public repository.
