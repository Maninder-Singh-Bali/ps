# Pixeloid Studio

Source snapshot of the Mac dashboard and Windows GPU-worker integration, 3 October 2026.

## Current build

- Manual PDF/image floor-plan workspace with calibrated source overlays and separate editable drafts.
- Shared wall junction geometry in plan and 3D; persistent merged-wall objects, segment editing, detach and undo/redo.
- Hosted door/window placement, automatic geometry-supported imported-opening attachment with explicit preview for ambiguous hosts, anchored width/height edits, wall elevation, live dimensions and alignment guides.
- Legacy window sill walls and opening lintels retained. Unknown heights remain assumptions; full-height glazing is preserved.
- Authenticated, certificate-verified Windows worker adapter; persistent image/video jobs, cancellation/reconnect/output verification and generation-phase limits.
- Native-1080p and 768×432 LTX preview presets remain distinct. Capture instrumentation code is included as prepared source, not an instruction to deploy or render.

- Wall, ceiling and floor surface design carries placements, dimensions, materials and reference previews into shared scene guides and generation manifests.
- Reusable 3D preview, independent metric/feet/inches units, trackpad navigation and direct return from surface design to the 2D floor plan.

## Develop locally

The Mac hosts the dashboard and CPU geometry tools. All configured AI inference runs on the paired Windows PC; do not install models on the Mac.

Use an isolated Python environment with `requirements.txt` and install the renderer's Node dependency from `package.json` (or the pinned `pnpm-lock.yaml`). No models or GPU runtimes are bundled.

For a blank loopback-only development dashboard:

```sh
python server.py --port 8777 --data /absolute/path/to/private/development-data
```

For an existing paired worker, supply a private config based on `remote.example.json`:

```sh
python launch_mac.py --data /absolute/path/to/private/project-data --remote-config /absolute/path/to/private/remote.local.json
```

The launcher detaches the dashboard from the launching terminal. Configure `PIXELOID_NODE` if Node is not on PATH. Choose an unused port and never open another running dashboard's data directory. The example IP addresses are documentation placeholders, not a configured endpoint.

Open `/floor-plan.html` to import a PDF/image, select a page, set scale and trace. Imported drafts stay separate by default. Explicitly linked manual projects feed the shared scene and invalidate stale outputs on geometry/design changes; the UI does not automatically activate an arbitrary draft. A fresh clone contains no apartment draft or project outputs.

## Checks

Run focused non-inference checks with the installed CPU dependencies:

```sh
python -m unittest discover -s tests -p 'test_manual_drafts.py'
python -m unittest discover -s tests -p 'test_wall_junctions.py'
python -m unittest discover -s tests -p 'test_opening_elevation.py'
node tests/test_trace_geometry.cjs
node tests/test_editable_junctions.cjs
node tests/test_wall_editing.cjs
node tests/test_merged_object.cjs
node tests/test_opening_position.cjs
node tests/test_opening_edit.cjs
```

Published geometry fixtures are synthetic. Private drawing acceptance checks remain outside this repository. Tests requiring a specific Windows runtime, GPU, installed model or capture-node source snapshot are separate; the focused checks above do not establish those capabilities.

## Preservation and deployment

No drawings, product references, scene geometry, project databases, generated media, pairing credentials, private operational reports or model weights are included. Runtime data and drafts must stay ignored.

Source publication does not deploy the Windows worker, restart ComfyUI, release models, approve outputs or authorize generation. Those actions require their own explicit authorization and compatibility checks. Keep externally owned services intact.

See `PIXELOID_STUDIO_PROTOCOLS.md` for interpretation/preservation rules and dependency notices under `dependency-licenses`, `model-notes` and `resources`.
