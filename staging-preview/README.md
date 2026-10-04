# Pixeloid synthetic HTTPS staging preview

This isolated static site uses newly invented apartment geometry only. It contains no private project data, production backend, authentication tokens, renderer or PC management routes. No sign-in is needed. Changes are stored only in the visitor's browser, under a staging-specific localStorage key. Reset demo clears only that key.

- Working browser code: Plan editing, wall/opening geometry, selection/merge, snapping, numeric units, elevation, undo/redo, 2D Surface Design and theme switch.
- Mocked: draft API and browser-local persistence. Edited wall fills use a simplified rectangle approximation instead of the production Python polygon resolver.
- Offline fixture: original 3D scene produced by the real geometry backend during build. It is read-only, not live. Changing geometry or surfaces blocks its use as a current Plan 3D preview. Furnish/Cameras show the baseline explicitly, with local orbit/zoom only.
- Unavailable: live backend validation/rebuilding, shared server saves, imports/uploads, product lookup, furniture placement, camera persistence, image/video/reference generation, approvals and worker/PC management.

Staging never modifies the Mac/PC deployment or any real project's generation allowances. It has no inference path. Hosting requests fetch static files only.

Source baseline: code-only commit 2903e030cc0b2302a5153fe9a3cd121179049d03. Preview-only adaptations are isolated from the deployed application. `preview-manifest.json` lists the static files and hashes.
