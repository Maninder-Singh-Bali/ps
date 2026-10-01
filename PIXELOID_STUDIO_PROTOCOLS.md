# Pixeloid Studio protocols

Version 3 · 1 October 2026

These rules apply to every project and imported plan. They govern interpretation,
editing and image guidance; they never authorize replacing a user's corrections.

## Native local workflow

- Normal operation stays in Upload, Review & 3D, and Images & Video. Backend jobs,
  service readiness, cancellations, retries and recoveries belong to the dashboard.
- Never send drawings, geometry, prompts or generated media to cloud inference or
  conversion. Missing local capability is an actionable limitation, not permission
  to use a remote fallback. Downloads require explicit in-dashboard approval of a
  pinned component, its size, storage and licence before transfer.
- Reuse an existing local service; never launch duplicates or kill another user's
  render. Serialize heavy local jobs and check available RAM, commit and VRAM.
  Memory thresholds are scheduling guards, not guarantees that every model fits.
- Completion, coverage, geometry validation and user review are distinct states.
  Interrupted analysis resumes checkpoints; uncertain render submission is reconciled
  with local history before any retry to avoid duplicate generation.

## Raster reconstruction and correction

- Extract wall evidence from original pixels. Compare enhanced evidence independently.
  Detection boxes, room labels and semantic guesses never become wall geometry.
- Retain masks, fitted paths, source transforms, endpoint/thickness uncertainty and
  individual ambiguous spans. The current CPU tracer uses thickness filtering,
  skeleton graphs and bounded line/arc/spline fitting. It is not trained segmentation.
- Keep weak exterior contours and candidate openings provisional. Do not close a
  doorway or open-plan transition merely to obtain a polygon. Connected free space
  is a room proposal, not a confirmed room or a floor slab.
- Show proposals over the original in the workspace. Save focused point corrections
  and undo/redo without changing source pixels. Preserve edits across rescans.
- Partial 3D must say partial and unverified. Do not manufacture missing walls, slabs
  or room geometry. A rendered GLB is not evidence of architectural correctness.
- Reliable thin-wall, furniture/stair and doorway separation still requires a local
  trained architecture segmentation component and reviewed, representative labels.
  Report held-out geometry metrics only when that annotation set exists.
- Image guidance uses saved geometry and a scene fingerprint. Current FLUX reference
  conditioning is soft; exported depth/normal guides do not yet enforce geometry.
  Compare generated architecture against the saved model before image approval.

## Automatic import

1. Preserve the original upload and its native vectors, units and page identity.
   Process PDF pages independently; never infer building scale from page DPI.
2. Initialize metric model settings immediately. Queue one background setup per
   page, deduplicating repeat requests. Use bounded local OCR, enclosure evidence,
   repeated strokes and available CAD layer hints. When the installed local
   upscaler and visual reader are available, queue enhancement and object reading
   after setup. Do not install/download dependencies during import. Serialize
   GPU work with rendering and release visual models after reading.
3. Propose room names, floor assignments and boundaries. Keep recognition
   evidence and uncertainty with the plan. A numbered legend describes types,
   not the number of physical rooms. A label rectangle is not a traced wall.
4. Apply proposals only to an untouched page. Recheck its source, drawing,
   structure review and sections after reading. If any changed, retain suggestions
   separately and keep the user's work. Other imported pages must not invalidate
   one another. Reader failure must preserve the upload and usable defaults.
5. Build 2D and 3D from the same identified geometry. Unknown strokes remain
   review evidence; do not extrude them as walls or invent furniture. Current
   reading combines conservative OCR/geometry with local semantic proposals.
   Neither is complete semantic reconstruction or automatic approval.

## Low-resolution plans and object recognition

- Preserve the original byte-for-byte. For raster plans up to 1600 pixels on the
  longest edge (2 megapixels maximum), create a cached 4x Real-ESRGAN reading copy.
  Record original and model hashes, dimensions, method and elapsed time. Larger
  images retain native resolution. A missing/failed upscaler falls back explicitly
  to the original; never report interpolated pixels as recovered facts.
- Keep original evidence alongside the enhanced reading copy for review. Read sections separately
  from overlapping object crops; map every crop location to the original page.
  Preserve the original scale regardless of enhancement resolution. Do not infer
  dimensions from invented detail or turn label bounds into walls.
- Recognize visible architectural, furnishing, sanitary, kitchen, lighting,
  decoration, landscape and equipment symbols. Support free-text object names
  beyond the library; suggest a library asset only for a supported match.
  Generic sofa/bed recognition must not invent seat counts or bed sizes.
- Use shape, internal details, labels and spatial context together. Repeated
  cushions and wardrobe shelves are not sufficient evidence for stairs. Room
  function alone does not prove an object is present. Unknown stays unknown.
- Retain uncertainty, source location, evidence and incomplete-pass warnings.
  Confidence is the reader's estimate, not calibrated accuracy. Deduplicate
  overlapping reads without merging distinct adjacent chairs. Review proposals
  before adding geometry. Never overwrite saved corrections on a rescan.
- Keep estimated scale explicit until supplied dimensions calibrate it. Object
  recognition is not exhaustive and cannot guarantee knowledge of every object.

## Scale and anthropometry

| Setting | Studio default |
| --- | --- |
| Wall height | 3.00 m per floor |
| Human reference | 1.6764 m / 5.5 ft |
| Walking eye level | Human height minus 0.11 m; normally 1.5664 m |
| Vertical perspective field of view | 60 degrees |
| Chair and sofa seat surface | Approximately 0.45 m |
| Dining/work table top | Approximately 0.75 m |
| Kitchen counter top | Approximately 0.90 m |
| Stool seat for a 0.90 m counter | Approximately 0.65 m |

These are editable visualization defaults, not universal human averages,
measured building facts or building-code requirements. Accommodate the intended
occupant, mobility needs and actual product dimensions when supplied.

Scale priority: saved floor measurement, explicit saved model scale, declared
CAD units, reviewed furniture dimensions, reliable linked product dimensions,
known library proportions, then an explicitly uncalibrated placeholder. Retain
the source of every estimate. CAD declarations also need a known-length check.
Use one drawing scale across axes for uncalibrated plans; preserve explicit
calibration. Never infer plan width from wall height or human stature alone.
Never let moving a chair silently recalibrate a saved plan.

Reject non-finite, zero or negative dimensions. Convert feet/inches/cm/mm before
comparison. Prefer multiple compatible anchors; exclude distorted footprints,
merged symbols and conflicting product variants. Product photos identify design,
not room dimensions. A sofa's piece count is not its seat count. Unresolved
retailer discrepancies require review; do not silently choose the convenient size.

## Furniture and ergonomics

- New library assets use physical dimensions and the current plan scale.
  Recognized source footprints are evidence: do not automatically rearrange them
  to fit a preferred layout. Explicit Balance furniture operates as an undoable
  edit and preserves position, rotation, object identity and module counts.
- Sofa extension changes seat modules with consistent depth and pitch; chair
  extension repeats chairs. Keep round objects round and retain rigid furniture
  proportions. Single-axis resizing must not deform cushions or stretch chairs.
- Preserve reviewed dimensions ahead of estimates. Check seat/table and
  stool/counter relationships together, including knee clearance and reach.
- Check overlaps, door swings, window access, circulation, passage pinch points,
  stair landings/headroom and wall/ceiling mounting. Existing placement checks
  cover known geometry and overlaps; they are not a complete ergonomic or code
  checker. Do not claim an unimplemented clearance check has passed. Use local
  requirements and occupant needs for numerical clearance decisions.
- Lights, paintings and wall/ceiling objects retain mounting elevation and
  orientation. Stair rise, run, width, direction and floor connection must be
  coherent; unresolved connections stay flagged rather than guessed.

## Architecture, floors and editing

- Group sections by floor; stack visible floors by their heights. Hide/show is
  a view setting, never deletion. Preserve courtyard and stair voids; do not
  fill an upper-floor opening merely because a lower-floor section is visible.
- Door/window insertion splits the host wall, keeping both views synchronized.
  Preserve curved walls. Section rectangles, swing arcs, hatching and stair
  treads are not wall segments. Replace source outlines only when an identified
  asset covers the same object; preserve the original source for inspection.
- Furniture, walls, openings, cameras and assets share the inline workspace.
  Keep controls compact, show contextual object names, and keep both viewports
  aligned. Selection, group transforms and undo/redo use the same object IDs.
- Validate every section before an atomic save. Do not save half a multi-section
  edit. Build the shared preview once after validation, not once per draft.
  Expensive readers run outside the project lock; no slow GPU work on import.

## Image generation and verification

Use the same saved geometry, physical scale, floor heights, eye level, camera,
openings and object placement for the viewer and image guidance. References
define appearance; they must not replace the scene's layout or introduce their
photographed room. Save scale provenance with the scene. Keep review gates for
uncertain architecture, unreviewed furniture and conflicting references.

No automatic generation, approval or destructive replacement follows upload.
Reference conditioning is not a guarantee of exact geometry: inspect generated
images. Verify changes with import/restart/idempotence tests, invalid dimension
cases, multi-floor save tests, undo/redo and viewer regression checks. Measure
performance with representative plans and keep user projects out of fixtures.

## Runtime entry points

- `plan_setup.py`: import defaults, background reading, guarded atomic apply.
- `scene_scale.py`: metric provenance, height/eye defaults and scale estimates.
- `plan_reading.py`: shared local evidence collection and review semantics.
- `furniture-library.js`: physical presets, repeatable modules and balancing.
- `furniture_blocks.py`: shared validation and atomic plan saves.
- `shared_floor.py`: common geometry for 3D viewing and image guidance.

Keep this protocol synchronized with behavior; record limitations explicitly.
