# ui7 editing verification

Exact source commit: `preview-manifest.json`. Detailed implementation and acceptance report: [Editing verification](https://github.com/Maninder-Singh-Bali/ps/blob/dashboard-review/docs/EDITING-UI7-VERIFICATION.md).

The real 16-section apartment was tested only in a private isolated copy: room focus, chair placement and 3D movement/rotation, wall/ceiling-hosted surface edits, undo/redo, save/reopen, reference assignment, invalid placement feedback, selected units and 1280×720 layout. Saved canonical records and reference bytes were checked in offline scene manifests. Original project and camera records remained unchanged. Ordinary generation readiness still requires existing camera/review checks; no approvals or inference were used.

94 Python tests and 10 focused Node suites passed. Staging adapter checks cover browser-local edits, revisions, synthetic references, simulated jobs and save fault states.

This Pages deployment contains production browser components with a staging-only adapter. Architecture and camera image previews are static baseline fixtures. Furniture proxies update locally. Surface edits persist locally; the public preview does not run a production geometry rebuild or backend validation. All job activity is SIMULATED. No live backend, private data, uploads, external product lookup, PC access, inference or generation allowance changes are available.
