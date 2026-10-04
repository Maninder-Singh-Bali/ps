# ui6 polish verification — 2026-10-04

Baseline: source `b87d62e11748648e65fa22e2de0074a84e40b7f5`, Pages ui5 `6974eae29710c36b8a096ceff15f4905ea528589`. Exact released source is in `preview-manifest.json`.

These are frontend checks with synthetic browser-local responses. They do not prove production backend, shared geometry, inference or video generation correctness.

## Changes

- Shared production Video component separates Create next video from Review selected output. Approval/download identify the saved version; output metadata is independent of next-job settings. Adaptive player and paired Room/Camera selectors preserve laptop space; creation appears before the player on narrow screens.
- Testing is a header action opening a bounded keyboard-dismissible dialog, rather than a floating panel over actions.
- Shared furniture component has an Add furniture catalogue dialog; selected physical dimensions/actions remain beside the canvas. Search/category survive closing/reopening. Reference details open explicitly. Browsing is click-to-add, then move on canvas; catalogue drag-out is not offered.
- Generic architecture labels are off initially, explicit preferences persist, contextual furniture labels show dimensions, and room/object identification remains. Mock validation is one compact disclosure; actionable save errors remain visible.
- Narrow toolbar wrapping and compact stage buttons prevent horizontal overflow. Existing dark default and explicit theme preferences remain.

## Actual browser checks this round

- **Layouts:** Video and selected-furniture layouts at 1280×720, 1366×768, 1440×900 and 390×844. No document horizontal overflow in these checked layouts. Video create actions remain above the player on narrow screens; desktop review actions fit without a progress panel. With job progress, review is reachable by scrolling. Native dialogs fit the viewport and scroll internally. Plan/Surfaces narrow toolbar overflow was found, fixed and rechecked at 390×844.
- **Video:** changed next preset to native eight seconds while saved Version 1 metadata remained two seconds/768×432. Larger-view dialog opened and dismissed. Simulated queued progress, cancellation, same-job recovery and inline cancellation worked. Missing current approval visibly disables creation after a synthetic scene edit. No real job submitted.
- **Furnish:** catalogue search/category, Chair addition, selected physical width 0.7 m and rotation 30°, Apply, save/reload retained values; reopen retained search/category. Duplicate/delete and bundled reference assignment persisted through save/reload. Selected contextual dimension label and explicit All object labels preference worked. Precise transforms, rather than mouse dragging/resize handles, were used in this round.
- **Save recovery:** explicitly armed rejected save, confirmed Not saved and retained edits, retried successfully, reloaded retained edit. Adapter tests separately cover delayed/conflicting saves.
- **Navigation:** all six stages opened; primary controls accessible. Cameras floor change remained Cameras, Upper lounge saved-view selection survived reload, and Back/Forward restored Cameras/Images. Plan/Surfaces handoff retained floor 2.
- **Images:** discarded Version 3 was kept through comparison; selector said Kept for review, distinct from approval.
- **Accessibility/appearance:** catalogue and Testing Escape dismissal return focus to their opener; keyboard focus has a visible 2 px outline. Light choice survived reload and Dark was restored. Dark/light appearance checked; no media inversion. No application-origin warnings/errors observed in the local verification tab.
- Before/after 1280×720 screenshots captured for Video and selected furniture. Screenshots are verification artifacts, not private project content.

## Automated checks

- Eight JavaScript suites pass: workspace selection, camera view, furniture history, editor save/navigation races, Surface navigation, video presets, new review-layout/output-identity checks, and new label-preference checks.
- Twelve staging-adapter groups pass, including browser-local saves, review transitions, masks, references, revision conflicts, reset races, simulated jobs and external/backend request blocking.
- Bundled JavaScript syntax checked. Published manifest and code-only static artifact checked before deployment.

## Limits / not re-exercised

- No exhaustive catalogue, touch-device, screen-reader, native browser-chrome zoom or cross-browser testing. Narrow workspaces still require vertical scrolling; Plan uses a toggleable inspector overlay.
- Plan tracing/junction edits, Surface placement/alignment, camera placement, image masks, MP4 playback, native fullscreen, furniture drag/resize handles and all unit conversions were covered in earlier work but not freshly rerun here. This release checks their workspace entry points and relevant isolated regressions only.
- Repeated video submission while an existing simulated job is active was not tested; queued cancellation/recovery was tested. Real output approval routes were not exercised.
- Architecture and camera previews remain static fixtures; furniture proxies update in the actual browser renderer. Mock saves/reviews have no backend validation. Simulated outputs reuse bundled samples irrespective of camera, presets, references or masks.
- No production projects, approvals, allowances, credentials, worker services or PC operations changed.
