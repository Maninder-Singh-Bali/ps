# Synthetic UI-testing staging

Production UI source commit: see `preview-manifest.json`. This is the consolidated **ui8** build. See [the verification report](https://github.com/Maninder-Singh-Bali/ps/blob/dashboard-review/docs/EDITING-UI8-VERIFICATION.md).

Open `?preview=ui8&project=synthetic-ui&stage=furnish&scenario=multi-room`, then click **Load scenario** in Testing controls. The new 16-room, two-floor fixture has its own browser-local dataset. The earlier basic fixture and saved work remain available by choosing **populated**. Reset affects only the currently selected synthetic dataset.
All six workspaces use the production browser components. Staging-only transport, fixtures, testing controls and clear simulation labels are added at build time; deployed production files are never edited.

No live backend is deployed. Synthetic saves, revisions, reviews, masks, camera settings, progress and jobs are stored in each visitor's browser. Testing controls select populated/empty/loading/success/failure/disconnected states and save faults. Reset affects only this synthetic namespace.

Two invented floors include openings, shared corners and a production-generated rounded corner. Furniture uses the production catalogue and client meshes. References, images, textures and a two-second MP4 are programmatically drawn fixtures, not generated output. All dimensions are assumptions.

Limitations: joined-wall fill after edits is a simple browser approximation; 3D architecture and camera image previews are static baseline fixtures. Furniture proxies still move through the real browser renderer. No production shared-scene rebuild, collision/structural validation, real upload/product lookup, inference, worker controls, service management, production approval or generation allowance operations exist. Unsupported buttons are disabled with a reason.

Mock frontend tests are not evidence that production backend, shared geometry, inference or video generation works. No original plan images, supplied style/product photos, outputs, credentials or PC addresses are included. The user-authorized Heritage inspection scenario includes an allowlisted copy of its constructed geometry, furniture, surfaces and camera; it is separate from the invented scenarios.

Build from the code-only checkout using Python with the project dependencies (including Pillow and av), Node on PATH, and `PIXELOID_SOURCE_COMMIT` set to the checked-out commit: `python staging-preview/build-ui.py`. `PIXELOID_NODE` optionally specifies the Node executable. Output is `verification/https-staging-ui-20261004/site`. Only this static output belongs on Pages. Never serve the production Store or backend for this preview.

## Constructed Heritage residence inspection

Open [the inspection handoff](https://maninder-singh-bali.github.io/ps/heritage.html), then **Open furnished residence**. This explicit link selects the separate `heritage` dataset without resetting saved edits. The other scenarios remain available through Testing controls.

The checked-in `fixtures/heritage-courtyard.json` contains only allowlisted geometry and editing state from the constructed demo, republished with the user's authorization. No build step reads a production Store. Source-image bytes, reference thumbnails, credentials, worker configuration, local paths and original project IDs are excluded. Furniture public source links remain metadata. Original reference images are intentionally absent, which limits source/style comparison.

The adapter uses the saved 0.032 m/pixel assumption and 3 m wall height, not the invented scenarios' 0.01 m/pixel. Architecture/surface meshes are an offline production export, not a browser rebuild. Meshes are loaded from the fixture rather than duplicated into localStorage on every save. No image/video job or output review is allowed for this scenario.
