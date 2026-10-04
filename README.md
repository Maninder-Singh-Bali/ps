# Synthetic UI-testing staging

Production UI source commit: see `preview-manifest.json`. The ui7 editing update builds on source `198a701c2098241a2e0578b5f761169de7caa9c5`. See `docs/EDITING-UI7-VERIFICATION.md` for private-copy testing scope and limitations.
All six workspaces use the production browser components. Staging-only transport, fixtures, testing controls and clear simulation labels are added at build time; deployed production files are never edited.

No live backend is deployed. Synthetic saves, revisions, reviews, masks, camera settings, progress and jobs are stored in each visitor's browser. Testing controls select populated/empty/loading/success/failure/disconnected states and save faults. Reset affects only this synthetic namespace.

Two invented floors include openings, shared corners and a production-generated rounded corner. Furniture uses the production catalogue and client meshes. References, images, textures and a two-second MP4 are programmatically drawn fixtures, not generated output. All dimensions are assumptions.

Limitations: joined-wall fill after edits is a simple browser approximation; 3D architecture and camera image previews are static baseline fixtures. Furniture proxies still move through the real browser renderer. No production shared-scene rebuild, collision/structural validation, real upload/product lookup, inference, worker controls, service management, production approval or generation allowance operations exist. Unsupported buttons are disabled with a reason.

Mock frontend tests are not evidence that production backend, shared geometry, inference or video generation works. No private project files, original plans, outputs, credentials or PC addresses are included.

Build from the code-only checkout using Python with the project dependencies (including Pillow and av), Node on PATH, and `PIXELOID_SOURCE_COMMIT` set to the checked-out commit: `python staging-preview/build-ui.py`. `PIXELOID_NODE` optionally specifies the Node executable. Output is `verification/https-staging-ui-20261004/site`. Only this static output belongs on Pages. Never serve the production Store or backend for this preview.
