# Editing workflow update (ui7)

This release was developed against an isolated copy of a real 16-section apartment, with renderer/service access disabled. The original apartment, outputs, camera records, approval records and paused phase were not edited. Public preview data is synthetic only.

## Reproduced causes

- Same-floor section changes updated the selected row but retained the previous view extent. Fast clicks could also be dropped while an asynchronous check was running. Room changes now reset editor framing and coalesce pending selection to the latest requested room.
- The 3D viewer exposed orbit and placement picking, but had no canonical drag lifecycle for selected objects. New manipulation callbacks update the existing objects; camera navigation stays separate.
- Solid previews lost ceiling and edge-mask flags during mesh conversion. Internal coplanar seams and overlapping horizontal finish regions also contributed to excess lines/occlusion. Mesh conversion retains those flags; coplanar seams are suppressed; later horizontal surface coverage replaces earlier coincident coverage while preserving declared voids.
- The catalogue and secondary object popup obscured the work. Surface editing reused structural tools and accumulated controls in long accordions.

## Numbered requirements

1. **Room focus:** all 16 section buttons were exercised in the apartment copy. Each changed the active room, boundary, 2D view box and 3D focus bounds. Rapid Bedroom 2 → 3 → 4 clicks settled on Bedroom 4. Whole apartment and Selected room are separate actions. Saved camera records were compared and remained unchanged.
2. **Direct 3D editing:** selected furniture supports Move/Rotate, a manipulation indicator, floor-plane movement, host-plane wall movement, ceiling placement/drop, precise dimensions and snapping. Surface items use the same surface-local records as the 2D editor. A chair was moved and rotated in 3D; wall painting and ceiling pendant were moved on their hosts. One-drag undo/redo and Escape rollback were exercised. Backend validation rejects incompatible host/floor/height/span changes.
3. **Catalogue:** Add furniture opens a bounded, non-modal catalogue next to the canvases. Filters persist, selection shows a placement preview, repeated click placement stays armed until Escape, and closing the catalogue restores the selected-object inspector. Chair placement was exercised in Bedroom 1.
4. **References:** thumbnail/empty state, choose/upload/replace/remove and product URL are upfront; detailed metadata is secondary. A bundled synthetic image was uploaded and assigned to the chair; another was assigned to the ceiling item in the private copy. Their original bytes and IDs were checked offline after saving.
5. **Dimensions:** compact proxy width/depth/height, position and rotation use the selected units. Product dimensions are separate evidence, converted explicitly to the selected units. Applying reviewed dimensions is a distinct action. In the apartment copy, a proxy-only resize left the reviewed product dimensions unchanged.
6. **Placement:** canonical transforms, host attachments, height/elevation and optional additional design instructions appear in shared scene manifests. Existing notes remain intact. No spatial intent such as “faces the table” is inferred.
7. **Viewing:** Solid is the new-session default. X-ray, Edges and Cutaway are separate controls; explicit preferences persist. View preferences are not scene inputs. Staleness tests confirmed geometry/reference changes invalidate snapshots while surface visibility settings do not.
8. **Utilities:** occasional global utilities moved into the header, retaining activity access. The empty full-height utility strip is removed; stage tools remain available.
9. **Toolbar:** responsive groups align checkboxes, selectors and Save. The 3D control row wraps rather than clipping. The apartment copy was inspected at 1280 × 720 in dark and light themes.
10. **Surface tools:** Select, Material, Add item, Move/Rotate and shading replace construction tools. Align/distribute operates on selected surface items; live dimensions and explicit Advanced boundary editing remain available. Plan is the route for structural editing.
11. **Surface workflow:** room → wall/floor/ceiling → face → Material/Items. Wall faces can be picked on the plan; horizontal faces use explicit saved boundaries or an explicitly requested room extent. Boundary/evidence options are secondary. Face/tab changes preserve data. Clicking an item opens its item inspector.

## Actual apartment-copy checks

- Chair placement, direct 3D translation and 30° rotation, undo/redo, Escape, exact saved transform, reference assignment, explicit product dimensions, independent proxy resizing and normal save/reopen.
- Wall painting movement: wall-local X and mounting height changed; undo restored both; redo/save retained its host.
- Ceiling pendant: width, local position and drop changed; 3D movement retained the drop; save/reopen preserved dimensions and reference. An excessive drop was rejected with a specific message.
- Oversized furniture was rejected with room-footprint feedback. Escape in a numeric input did not deselect/delete the object.
- Shared scene manifests contained the exact saved furniture and surface records. Three saved surface-reference byte hashes matched their materialized input files. Original project/draft JSON hashes and saved cameras were unchanged.
- Read-only diagnostic preview used the existing living camera and actual shared geometry. It is **not a generation-ready guide**: ordinary preparation still reports existing review requirements. Bedroom 1 also has no saved camera. No approvals were manufactured to bypass either check.

## Automated verification

94 relevant Python tests (furniture save/mesh/attachment, surfaces, reference inputs, scene staleness/evolution and shared-floor health) and 10 Node suites (viewer interaction, coplanar seams, library dimensions, navigation/startup/selection, surface editing and walk controls). New tests cover one drag/one commit, cancellation, host constraints, product/proxy separation and overlapping room finish coverage with void preservation. Staging adapter tests cover synthetic transport, persistence and fault states.

## Limitations

- Room focus uses saved section extents. These are editor bounds, not certified room geometry. A room-derived horizontal boundary is marked for review; unusual boundaries and voids still need explicit inspection.
- Furniture placement checks mapped room/host geometry; this is not comprehensive clearance, structural or collision certification. Existing unhosted legacy decor is not silently assigned to an arbitrary wall.
- Wall-mounted furniture orientation follows its wall; arbitrary rotations away from that host are rejected. Surface-local artwork can rotate in its face plane. Furniture multi-object 3D dragging is not included; surface multi-selection alignment remains available.
- Reference/texture meshes are proxies and sampled texture approximations, not exact product models. External product lookup was not exercised.
- The public Pages build has no real backend. Architecture/camera previews remain explicitly labelled static fixtures; furniture proxies update in the browser. Surface preview rebuild and server validation cannot be proven by its mocks. Uploaded private files and external lookup are disabled; use bundled references.
- Original Mac/PC deployment was left running unchanged. Updated code is in the code-only release and isolated test build. No inference, PC communication, service/model operations or generation-allowance changes occurred.
