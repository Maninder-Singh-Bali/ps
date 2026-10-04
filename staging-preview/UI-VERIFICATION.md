# ui8 consolidated editing verification

Exact source commit: `preview-manifest.json`. [Full checklist, screenshots and limitations](https://github.com/Maninder-Singh-Bali/ps/blob/dashboard-review/docs/EDITING-UI8-VERIFICATION.md).

The real 16-section apartment was tested only in an isolated private copy. Browser checks covered room selection, 2D placement, 3D select/move/rotate, wall/ceiling-hosted edits, undo/redo, cancellation, save/reopen, reference upload, explicit product sizing, independent proxy sizing, invalid placement and shared scene inputs. Original data, source and cameras were unchanged.

The public multi-room fixture was exercised across both floors, stage/history navigation, saved references/transforms/finishes, rejected/delayed/conflicting saves, static camera selection, local image approval and simulated video completion/cancellation/recovery/reconnect. Layouts were checked at 1280×720, 1366×768, 1440×900 and 800×720. 94 Python tests, 10 editor Node suites, video preset checks and 14 staging-adapter groups passed.

Public previews use production UI components with a browser-local adapter. No real backend is deployed. Architecture and camera previews are static; furniture proxies update locally. Surface edits persist without a production geometry rebuild. Uploads, external lookup, PC/worker operations, inference, production approvals and allowance changes are unavailable. Frontend mock tests do not validate any of those systems.
