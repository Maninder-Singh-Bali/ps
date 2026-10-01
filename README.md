# Pixeloid Studio

**Source-only review snapshot.** Start with [REVIEW_HANDOFF.md](REVIEW_HANDOFF.md) and [SOURCE_SETUP.md](SOURCE_SETUP.md). Client plans, private local configuration, databases, generated media, runtime bundles and model weights are intentionally absent. The installed-package description below does not mean a fresh Git clone includes those dependencies.

Local architectural image and video dashboard. Open **Launch Pixeloid Studio.cmd**, then use http://127.0.0.1:8777 in any normal browser. It runs without Codex, a cloud account or API keys. The bundled runtime contains Python, image/video readers and the Node/sharp drawing engine. The launcher reuses the existing local ComfyUI server at port8190. If it is offline, it can start the configured installation after checking that no other ComfyUI process is starting. It never stops or restarts a shared renderer. Installation paths and auto-start are in studio.local.json.

## Workflow

Use **Upload → Review & 3D → Images & Video**. Upload images, PDF pages or model-space DXF. DWG is explicitly unsupported until a compatible local adapter is validated. The dashboard automatically queues preparation and local analysis, retains original evidence, and exposes uncertain boundaries in the existing split workspace.

**Setup** connects installed local components, checks hardware and required model files, and starts the reader/renderer. No normal-user terminal or external ComfyUI interface is required for installed capabilities. Approved downloads have explicit size, storage and licence information, resumable transfer and checksum verification. The current download catalogue contains one FLUX diffusion weight; a complete first-machine dependency/model installer remains unfinished.

Boundary review now includes original-pixel path proposals, curve fitting, point corrections, undo/redo and a synchronized partial 3D draft. The curved residence is not fully reconstructed: thin walls/glazing, openings, room topology and some furniture conflicts remain unresolved. No detection box is converted into a wall. Native curves, polygon floors/voids and reusable GLB/scene exports are supported where actual geometry is available.

Materials, furniture references, saved camera guidance, local FLUX generation, image review, local LTX generation, video playback and download remain in the application. Expensive image/video generation never starts merely because a plan was uploaded. Images must be approved before video. Generated media can still invent architecture: the current FLUX test failed spatial fidelity despite a successful local render, and was rejected in review.

Read [Implementation report](IMPLEMENTATION_REPORT.md) for measured results and remaining work, [Checklist](IMPLEMENTATION_CHECKLIST.md) for milestones, and [Studio protocols](PIXELOID_STUDIO_PROTOCOLS.md) for project-wide rules.

## Plan recognition and continuity limits

Default plan analysis is Windows OCR and room-label matching. It is **not a structural floor-plan vision model**. It cannot reliably infer every unlabelled room or count all repeated bedrooms from a legend; suggested areas are based on labels, not traced walls. Confirm or correct the map. Settings optionally supports an already-installed local Ollama vision model for additional room-boundary proposals. No cloud AI service is used and no vision model was installed with this dashboard.

Room and product image references and a consistent seed guide FLUX, but do not produce a coordinated 3D model or guarantee exact object identity, camera continuity or material fidelity. Review each output. Uploaded references retain their original pixel dimensions; outputs are sampled at 1920×1088 and cropped by 4 rows on each edge to 1920×1080. There is no output upscaler. Conditioning references may be resized. Native resolution alone does not eliminate generation artefacts.

The initial villa project contains imported draft areas and previous candidates. Nothing is pre-approved. The rejected slider view was excluded. The draft count includes labelled sections, not all unlabelled service spaces.

## Storage and connections

- Source: this directory. User projects, uploads, full-resolution outputs, workflow JSON, history and approval records: `data/`.
- Local state is persisted atomically in `data/studio.json`.
- FLUX and LTX API templates are in `templates/`. Each actual render saves its exact workflow, prompt, history and resolution provenance under its project/job directory.
- One owned render runs at a time, waiting for the shared ComfyUI queue and memory guards (12 GB available RAM, 20 GB commit headroom). A saved prompt is monitored rather than duplicated on restart.
- Ambiguous submission failures require inspecting ComfyUI history before retrying. The app will not automatically resubmit them.
- Engine configuration changes are blocked while activities run. References edited during a render make its output ineligible for current approval; the output is preserved.
- Idle model release is enabled by default and only runs after an owned render when the shared renderer queue is empty.
- The web server binds only to 127.0.0.1. Local media is served by asset IDs. There is no remote login or network exposure.

## Requirements and maintenance

Uses the bundled `runtime/python` and `runtime/node` for the dashboard, including Pillow, requests, PyAV and sharp. Small dependencies websocket-client and pypdfium2 are bundled in `vendor/` with their package licences. Windows OCR provides default plan label reading. The separate ComfyUI installation uses its own configured Python and must have the FLUX.2 Klein 4B and LTX2.5 model files named in the templates. The release archive includes dashboard dependencies, but does not duplicate installed model weights or contain user projects.

Run checks with the embedded Python: `python -m unittest discover -s tests -v`.

This release generates and reviews individual room images and clips. Full-film assembly, piano soundtrack, Instagram export, guaranteed 3D consistency and a universal model installer are not included. Raster wall tracing is provisional and requires focused review.


## Prompt help and project locations

Enhance prompt is available for reference prompts, room direction and project direction. It is a local spelling and structure helper, not a language or vision model. Compare the original and editable suggestion, apply it, or undo it. It does not save notes or start generation automatically and does not infer dimensions from images.

New project has a Save location field and a Windows folder picker. The app creates a unique project folder inside the chosen location. Project files in the sidebar shows the current path; Change save location copies the existing project before changing future writes. Originals remain at their prior location. Copy progress is displayed and active project jobs block relocation. If copying fails, the original project remains active; an incomplete copy is labelled in the destination.

Projects using the new layout store Floor_Plans, Rooms (with Room_References, Furniture_References, Generated_References, Images and Videos), Supporting_Files, Exports, and project.json inside the selected folder. Room folders keep stable names after room renaming. project.json is an index of rooms, assets, jobs and review records with project-relative file paths where possible; reopening/importing this index in another installation is not yet exposed in the UI. The app's data/studio.json remains its central workspace index. Migrated projects preserve previous supporting files under Supporting_Files/Previous_Location. A selected location holds the dashboard's copies; ComfyUI retains its own input/output working copies.


## Drawing correction, area and scene sunlight

Refine drawing opens the selected section. Add missing walls, doors, windows or detail lines; select existing SVG elements to move, resize, rotate or remove them. Use Undo/Redo and original overlay for comparison. Door endpoints define its hinge and closed leaf; Flip changes the swing. Room boundaries & areas opens the polygon editor with movable corners, redraw, new sections and void exclusions. These boundaries remain explicit: editing a wall does not silently recalculate room partitions.

Area estimates support percentages only, length and breadth, one marked real length, or a known total area. Metres and feet are supported. Each floor has its own calibration. Overlaps are counted once in covered area, with the unassigned remainder shown separately. Suggested bounding boxes must be refined before treating them as reliable areas.

North is unset until the user confirms it. The compass supports any angle clockwise from drawing-up. Optional latitude/longitude, date, local time and UTC offset calculate approximate sunrise, sunset, sun azimuth and elevation locally using NOAA general solar equations. Confirm the UTC offset for the location/date, including daylight saving. No geolocation lookup or external location transmission is performed. Use scene sunlight explicitly to send lighting guidance to FLUX; LTX uses the approved still and holds that lighting steady. This is not a physical daylight simulation: occlusion, weather and terrain are not computed.

Corrections are saved as versioned SVG/JSON and an architectural guidance PNG under Supporting_Files/Drawings. Originals are preserved. Architecture-only guidance excludes old drawn furniture, then adds the saved furniture markers for generation. Geometry edits require room-map review; changed inputs invalidate image/video approval. The model can still fail to obey soft reference conditioning, so output review remains required. A fixed seed alone cannot enforce identical geometry.

Vector rasterization uses the application's own runtime/node and sharp libraries. It does not use Codex runtime folders. No custom model nodes are required. Each job stores its exact API workflow and scene-lighting metadata. Full image/video jobs generate at1920x1088 and crop to1080; the vector guidance raster is not an output upscaler. Small surface cleanups use an unresized native-pixel context crop, generate only that patch, then composite it into the original native1080 master. Their saved surface_cleanup record states the context dimensions and preservation scope.

Progress uses real renderer events. Total elapsed includes waiting; Render time starts at input preparation. Completed times remain fixed. No remaining-time countdown is fabricated when an estimate is unavailable.

## Shared scene and protected edits

Room references → Consistency controls selects an explicit master (original room reference or a generated image from the same room, including a rejected candidate). Keep room structure starts FLUX sampling from the master’s encoded native pixels with a shortened noise schedule. It remains generative, so geometry must be reviewed. Edit selected area only additionally applies a noise mask and composites the master back outside a user-drawn rectangle. The exterior is checked pixel by pixel before the result becomes available for approval. Include the old object, new footprint and affected shadows in the rectangle. Local edits preserve surrounding illumination; full-scene solar changes are not applied in local mode. These modes require a 1920×1080 source; there is no enlargement. Conditioning pads four rows above and below; output crops those rows.

Each queued room generation records a shared scene fingerprint: master and reference content hashes, floor plan, corrected drawing, area calibration, placements, scene time, direction, seed and edit controls. Changes invalidate the queued work or approval. LTX receives the exact approved image hash and parent scene manifest, pads rather than resizing that source, and conditions the first latent frame at strength1.0. This ties the saved inputs together, not the models’ internal geometry: video drift and altered objects within edit regions can still occur. Full clip review remains necessary. No production output is approved automatically.

Protected edits automatically prepare normal-language instructions with the selected area, known furniture references and preservation scope. The original wording remains visible. This local context compiler fixes common spelling mistakes; it is not a separate language or vision model. The exact prepared instructions are saved with each render. Locked-camera video also guides its final frame with the same approved image. All decoded frames are checked for valid dimensions, frame count and timestamps; texture/exposure observations are saved, never interpreted as automatic visual approval.

## Standalone checks and discovery

System check diagnoses local dependencies, model registration, workflow nodes, saved files and prolonged missing render progress. It provides recovery guidance rather than stopping processes or resubmitting ambiguous jobs. Logs are stored under logs/. The installed ComfyUI, GPU driver and model files remain external dependencies on this PC; they are reused, not duplicated into the dashboard runtime. Models and local rendering work without internet. The optional Ollama vision service is not bundled; Windows OCR and manual map correction work locally.

Discover products offers India/INR, international/original currency and both markets. Live built-in sources are Dekor Company and Olive + Wild. Public structured product links from other retailers can be verified by pasting a URL. Prices, availability, photos, dimensions when supplied and check timestamps come from retailer metadata. Unsupported, blocked or inspiration-only pages are not invented into buyable listings. Pinterest opens as inspiration search, not a price/stock source. Search results are ranked against saved text direction, not image similarity. Product selection saves its provenance and photo in the room. Confirm variants, delivery, fit and final price with the seller. No purchase or login is performed.

Saved site coordinates use a bundled GeoNames index to find the nearest named city/region entirely offline. This is approximate city proximity, not an exact address or a delivery guarantee. Exact coordinates are never sent for discovery; the optional nearby-shop link uses only the city/region and opens on user action. Geography attribution and license are in resources/GeoNames-LICENSE.txt.


## Plan fidelity review (2026-09-30)

Image review → Compare with plan displays the exact source section, saved line/marker corrections, any perspective guide, and selected output version together. It uses the job scene snapshot, not later room edits. Rejected images can be selected for protected refinement without approving them; the video approval gate remains in force.

For fully manually redrawn straight-line plans with up to three placed sofa/table/chair references, or an unfurnished architecture shell, the app can create a relative perspective conditioning sketch. It preserves marker centres and camera heading but uses illustrative wall, window and furniture heights. It is not a complete architectural reconstruction. Original/vector features must all have been explicitly hidden before this route is used. Window finishes and closed door leaves are visualization defaults. Other cases use the existing plan/reference route when input checks allow it. Neither route guarantees model compliance.

The local FLUX.2 Klein reference-role prompt was revised after consulting BFL's official layout, multi-reference, technical prompting and structured JSON guides. It names each input role, one subject per selected product and camera-relative facing. These are semantic instructions, not bounding-box locks. Physical dimensions and neighbouring-room geometry still need validated source data. Initial living tests failed with duplicate chairs and invented adjacent geometry. A corrected reverse-camera view now passes preliminary visual layout review; a separate unfurnished bedroom test preserves its guide openings. Both await user review; no video has been approved or rendered from these tests. They do not establish arbitrary-plan recognition or exact product reconstruction.

Room references → Plan check runs inside this application and also runs before queueing a room image. It checks plan review, unresolved symbols/landings, furniture centres against the true section polygon, measured footprints extending outside that polygon, walls overlapping openings, and open camera-facing edges without adjoining geometry. Low source detail and unknown dimensions are reported explicitly. Curved sections without a suitable perspective reference are blocked rather than replaced with a straight-wall approximation. These are deterministic input checks, not an AI visual inspection of generated outputs. The local detector remains a conservative heuristic; plan interpretation still requires review.

The multi-section QA pass exercised13 villa room sections and4 curved-plan space proposals without changing production inputs. Two distinct sections were rendered: furnished living and unfurnished bedroom architecture.117 Python checks passed. Render metadata distinguishes full native1080 generation from native-pixel patch cleanup; no output upscaler is used.

Official references:
- https://docs.bfl.ai/guides/usecases_editing_controlnets
- https://docs.bfl.ai/guides/prompting_editing_multi_reference
- https://docs.bfl.ai/guides/usecases_t2i_json_prompting
- https://docs.bfl.ai/guides/prompting_unified_technical


### Full-plan section continuity correction

The prior living candidate was rejected after checking the FULL original plan: its manually constructed guide incorrectly made the courtyard sliding boundary solid. Previous preliminary layout-pass notes are withdrawn. Native resolution and matching a guide do not establish plan accuracy.

Study structure now links adjoining sections through one shared feature. It checks common full-plan coordinates, feature contact with both section bounds, and contradictions between marked openings and drawn walls. Both section prompts receive the shared feature. Open-space relationships are explicitly continuous space without a dividing wall/door/partition; their review bounds are hidden on the plan to avoid resembling construction lines. The original uploaded drawing is displayed by default and is not rewritten.

Five draft links connect living, kitchen, dining, sliding boundary and courtyard passage on the original villa source. They remain unapproved. User correction confirms the two horizontal living/kitchen and kitchen/dining transitions have NO WALLS. No fresh render or video followed the rejection.126 Python tests passed after this update. These checks constrain saved inputs and prompts, not generative-model geometry; full-plan review remains necessary.
# Shared-floor verification and local visual reader

Use **Structure check** from Floor plan or Room references. All section views use the same plan-owned typed wall/opening segments and furniture coordinates. Room rectangles are never converted into walls. Save each camera on the full plan. The 3D view is schematic; default heights and uncalibrated scale are explicitly labelled.

**Read objects with local AI** runs Qwen3-VL 8B Instruct locally through Ollama. It reads the original full image with a selected native-pixel crop, stores measured timing and source identity, and returns unconfirmed proposals. Add predictions to the architectural study only after inspecting the report. Individual furniture features retain object type and seat count. This is an assisted reader, not verified autonomous interpretation of every floor plan.

The local reader requires `qwen3-vl:8b-instruct` in the configured Ollama service. The tested portable service resides in `runtime/ollama`; its models reside in the configured ComfyUI root under `models/vision/ollama`. It starts on demand when installed and releases model memory after inference. The default `qwen3-vl:8b` thinking variant was rejected for this structured-reading task after empty-answer and inaccurate-reading tests. No model weights are included in the source release.

Automatic structure repair only cuts explicitly drawn wall portions crossing narrow, confirmed openings/open connections. It never edits the uploaded image, never uses unconfirmed predictions as authority, and saves a versioned audit with undo. Untyped vector paths and uncertain symbols require correction in the dashboard. Generated stills and full video motion still require visual QA and user approval.


## Rough 3D block layout

Open **3D block layout** on a mapped section. The original scan is read locally on the CPU to propose plain, unclassified furniture boxes. Use move, resize, rotate and split to correct them; neighbouring symbols can merge and faint objects can be missed. The original plan is never modified.

Click a block to link an existing furniture reference or upload one directly, and describe its change in the adjacent popup. Save the draft, then confirm only after reviewing it against the plan. Each linked block supplies one product's placement, proportions and facing to the FLUX guide; image fidelity still needs visual approval. Unknown or unlinked blocks and stale geometry remain blocked for generation. Sizes are proportions until drawing calibration; preview heights are illustrative. No GPU generation is started by scanning, checking or saving a blockout.
