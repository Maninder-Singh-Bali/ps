# UI-testing preview verification

Date: 2026-10-04. Production component baseline: `2903e030cc0b2302a5153fe9a3cd121179049d03`.

This is frontend verification against a browser-local adapter. It is **not** evidence that the production backend, shared geometry rebuild, image generation or video generation works.

## Browser interactions checked

- Plan: both distinct floors load; baseline 3D for both; second-floor rounded corner; trace a two-segment joined chain (11 → 13 elements), undo (12), redo (13), save and reopen (13); selected window width editing, unit changes, delayed/rejected/conflicting saves retain edits.
- Furnish: production catalogue, add chair, select, drag, resize to 120%, rotate, duplicate, inspect properties, assign bundled reference, save/reopen, delete. New-item dimensions are finite and nonzero. Existing furniture meshes use the browser renderer.
- Surfaces: floor material, texture size and layout persist; assign bundled texture; ceiling pendant placement, size, duplicate and move; multiple-item selection and alignment; wall artwork dimensions/reference and save.
- Cameras: production plan placement, camera naming/height save, saved-view switching, camera selection in Images. Camera preview is explicitly STATIC.
- Images: multiple version/review states, parent/result comparison, close-up/full-room, reference and saved mask outline; draw region mask, save instructions/reference; local approval and keep-for-review. Rejection persistence also covered by adapter tests.
- Video: MP4 playback reports 768 × 432 and 2 seconds; preset selection, locked-camera state, simulated job progress, cancel, same-job recovery, disconnected/reconnect and failure state. All results reuse the sample clip.
- Testing controls: empty state, reset to populated, failure, disconnected and reconnect; save fault controls. The automated suite additionally checks loading/delay, success completion and reset racing an in-flight save.
- Themes: Dark default, Light/Dark switch and persistence across refresh. Focus rings and disabled action explanations remain visible. Material/reference/media colours are unchanged.
- Layout: desktop 1440 × 900, laptop 1024 × 768, constrained 960 × 600 (equivalent available layout area to a 1440 × 900 browser at 150%). Corrected staging grid overlap. A 150% content-zoom stress check was also performed; native browser-chrome zoom was not automated. Narrow layouts may require page scrolling.

## Automated checks

10 adapter test groups pass: floors/fillet fixture, Plan revisions, furniture dimensions/references, cameras, masks/reviews/comparison, simulated jobs, save faults/disconnect, reset/empty, reset versus delayed writes, and blocked API/external networking. All bundled JavaScript passes syntax checking.

MP4: all 48 frames decoded; 24 FPS; 768 × 432; 2 seconds. The clip is a programmatically drawn sample, not inference output.

Artifact scan: no user filesystem paths, private apartment/project IDs, local/PC addresses, private keys, GitHub token patterns or PC-management routes found. Only bundled static resources are requested by the adapter; no API server is deployed.

## Deliberate limitations

- No real backend functions. Saves, conflicts, reviews, source-image selection and jobs operate only on synthetic data in each visitor's browser.
- Baseline architecture in 3D and camera images are static fixtures. Edited Plan geometry does not trigger a server rebuild. The Plan 2D fill resolver after edits is an approximation. This is not a shared-geometry regression certification.
- No backend collision/structural checks, measured product sizes, worker operations, real inference, private uploads or online product lookup. Unsupported controls are disabled with explanations.
- Every simulated image/video result is a bundled sample regardless of camera, preset, reference or mask. Samples do not demonstrate adherence to those inputs.
- Test coverage is representative, not exhaustive across every tool, browser or combination of edits.
