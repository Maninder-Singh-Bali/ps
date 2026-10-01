# Native workflow implementation checklist

Working branch: `improvements`. The active installation and its projects are preserved. This checklist records implemented work and remaining gates; it is not a claim that the whole brief is complete.

| Milestone | Implemented | Remaining gate |
| --- | --- | --- |
| 1. Source and evidence | Original preservation, source metadata, PDF/DXF native identity, raster transforms, bounded local analysis with checkpoints | Mixed PDF content classification; deskew evaluation; validated DWG adapter unavailable |
| 2. Boundary proposals | Original-pixel masks, skeleton paths, line/arc/spline fitting, uncertain contours, opening candidates, connected-space proposals | Reliable semantic separation, thin walls, doorway reconciliation, room topology; trained model and reviewed annotations needed |
| 3. Editable shared geometry | Point correction and undo in source overlay, synchronized partial 3D, curve preservation, polygon floors/voids, GLB and scene/provenance export | Complete raster room/furniture reconstruction and final geometry clearance; consolidate legacy specialist editors |
| 4. Native local operations | Three primary stages, automatic import jobs, Setup, hardware checks, local service startup, serialized jobs, cancel/retry/recovery | Full first-machine installer; current approved-download catalogue contains one FLUX weight only |
| 5. Image/video validation | Actual local FLUX and LTX dashboard runs, persisted scene fingerprints, image approval gate, existing playback/export | FLUX geometry fidelity failed on synthetic fixture; depth/normal controls are exported but not enforced by the model |

Next accuracy work must improve measurable geometry, not repeatedly rewrite the vision prompt. Keep unresolved spans explicit; detection rectangles are never wall geometry.
