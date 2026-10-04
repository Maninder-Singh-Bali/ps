# UI review fixes — 2026-10-04

Reviewed Pages baseline: `33141fe7bbf3441880ff94dca58cf728539c44c0`. The updated production-code commit is recorded in `preview-manifest.json`.

These are frontend checks against synthetic browser-local responses, plus isolated unit tests. They do not establish production backend correctness, shared-geometry rebuilding or image/video generation.

## Browser checks in this revision

- **Plan:** both floors; floor-to-Cameras handoff; trace wall (11 → 12 elements), select, dimensions, undo (11), redo (12), save/reload (12). Set feet, save, return to Furnish; a 0.55 m chair shows 1.804 ft. Rounded-corner fixture loads on floor 2.
- **Furnish:** add sofa/chair, select, drag, precise width/height/rotation, duplicate, delete, assign bundled reference, save/reload. Selected inspector remains accessible at narrow width. Percentage controls remain in Advanced.
- **Surfaces:** select wall face, place painting, change width to 0.75 m, assign bundled reference, change finish, reject a save, recover with a successful save, reload retained changes.
- **Cameras:** place and aim a new camera, name it QA corner view, save and immediately select it, reload, switch floors and return, switch saved views and Images, browser Back/Forward. Floor changes stay in Cameras. Static preview is explicitly labelled.
- **Images:** switch versions, open parent/result comparison, full-room/close-up toggle and mask outline, draw/save a rectangular mask with instructions. Keep a discarded candidate: card, selector and comparison say Kept for review; current note no longer says discarded; prior decision remains in history. Kept is not approval.
- **Video:** sample playback (768 × 432, two seconds), source and preset selection, fixed preview motion, next-job preset survives source-triggered refresh, larger closable viewing dialog, disabled reason when a camera has no approved source. Simulated progress, cancel, recover same job, failure scenario, disconnect/reconnect and completion. No real job submitted.
- **Save controls:** selecting a fault does not apply it; explicit Apply does. Rejected/conflicting saves retain edits and show Not saved. Delayed saves show Saving before Saved; repeated submission is blocked while busy. Stage navigation protects unsaved edits. Scenario replacement offers Keep editing / Discard edits and replace data; Keep editing retains edits. Fault setting is independent of scenario/reset.
- **Appearance/accessibility:** persistent Light/Dark switch, 2 px keyboard focus ring, readable monochrome tool icons, unchanged media pixels. Desktop 1440 × 900, laptop 1024 × 768, narrow 640 × 800 and 390 × 844; no document horizontal overflow in the checked Video/Furnish layouts. Narrow editors require vertical scrolling. No application-origin console warnings/errors observed in the local verification tab.

## Focused automated checks

- Six JavaScript regression suites pass: workspace selection, camera interactions, furniture history, editor save/navigation races, Surface navigation, and video presets. Added per-room camera memory/direct-link/new-view checks and next-job settings persistence.
- Seven Python tests pass for review transitions/history and revision comparison.
- Twelve staging-adapter test groups pass, including review history, save faults, independent scenario/fault state, delayed-write reset races, camera persistence, simulated jobs and blocked backend/external requests.
- All bundled JavaScript passes syntax checking.

## Limits and cases not re-exercised

- This round used precise sizing; furniture resize handles, every Surface alignment tool, every rounded-junction edit and all catalogue objects were not exhaustively retested. Earlier coverage is not counted as a fresh pass here.
- Metric and feet were exercised in the UI. Inches use the same canonical conversion path but were not separately exercised in this round.
- Native OS/browser fullscreen differs in embedded browsers; the explicit larger dialog was verified. Touch devices, screen readers, native browser-chrome zoom and other browser engines were not tested in this round.
- Architecture/camera fixtures remain static; furniture proxies use the real client renderer. Plan changes do not trigger a production shared-scene rebuild in this preview.
- Saves, review decisions, conflicts and job responses have no real backend validation. Simulated results reuse bundled images/MP4 irrespective of camera, masks, presets or reference instructions.
- Production route integration, real worker operation and inference were not executed. Private project data, approvals, allowances and the Mac/PC deployment were not modified by these tests.
