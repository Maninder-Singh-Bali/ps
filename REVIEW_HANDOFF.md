# Pixeloid Studio — external review handoff

Tested source checkpoint, 1 October 2026. Start here when reviewing this repository with ChatGPT or another code-review tool.

## Latest checkpoint: source-scope fixes and bounded segmentation evaluation

**Decision: no segmentation integration and no successful furnished-plan acceptance.** Benchmark 16 still fails. The untouched automatic baseline and its hashes are preserved locally; no new geometry corrections were made to that project during this evaluation. The earlier benchmark history below is retained and describes the state before this checkpoint.

### Implemented and verified in source

- `source_scope.py` is the shared source contract for structure proposals, OCR, visual readers and raster reconstruction. It records original-source hash, panel IDs/floors, crop geometry, exact rounded pixel extents, crop-to-sheet transforms and monotonic scope revision. Reader/cache identities include this contract. Raster workers receive a sheet with excluded pixels blanked; semantic/OCR readers receive separate original-pixel crops. Enlargement is applied within each crop, and observations map back to original-sheet coordinates.
- Raster classification now proposes crops but cannot approve itself. One source review is required before its readers run; current heuristic confidence is insufficient to silently trust an entire raster sheet. Native vector inputs retain their native full-sheet scope unless an explicit source review exists; explicit native crops are honoured by the readers too. This is not a new DWG conversion capability or validation of CAD semantics.
- Source approval atomically saves the crop revision, cancels superseded jobs, invalidates dependent approvals and queues reconstruction followed by preparation. Preparation queues installed local semantic analysis. Duplicate current-scope jobs are suppressed. Existing manual drawing edits, reference assignments and reviewed evidence remain saved. Obsolete reports are retained for diagnostics but cannot install over current results; crop undo creates a new revision rather than reviving old jobs. Unchanged raster evidence no longer clears correction history just because timing/cache/overlay metadata changes.
- Exhausted detection with no remaining or failed regions cannot offer a useful resume. The Review control says Detector exhausted, Activity hides Retry for that terminal result, and both resume endpoints reject exhausted or obsolete work. Partial jobs with recoverable pending/failed regions retain recovery. No additional model calls were made against the saved benchmark-16 semantic detector.
- Tests exercise actual crop pixel contents at mocked reader boundaries, two-panel coordinate mapping and floor identity, automatic resumption, duplicate suppression, edits/crops changing during OCR, visual analysis and raster completion, resized raster-coordinate mapping, undo, failed-save rollback, stale/exhausted retry and classifier self-approval prevention. These are lifecycle tests, not proof of detector accuracy.

No candidate model, weight, added library, supplied image, annotation, overlay or private database is included in the repository. The working local Studio services were not restarted or reconfigured for this research evaluation. Backend fixes are in this source checkpoint; the already-running Python service needs a controlled restart before it uses the new backend modules. A browser reload verified that Detector exhausted is disabled and Resume analysis is absent. No new successful dashboard reconstruction is claimed.

### Isolated local candidate and separate licence checks

The explicitly approved research download was **Yytsi/floorplan-to-3d-walls**, ResNet34–UNet, four output classes, model revision `68843a3ab7b12aa03b23c36f955a0d8099b4e2ee`. The 97,851,168-byte `best.safetensors` file matched SHA-256 `d7f6a0fd06e2931aecfc8c4849192c5e153701578026efc78d9a6246731a8d6c`. It loaded with strict state-dictionary matching. No extra ImageNet weight download was performed. Only SMP 0.5.0 and timm 1.0.30 were added, into a separate evaluation-only library folder; existing runtime packages were unchanged. The whole private evaluation occupies about 129 MB, below the approved 1 GB allowance. No drawings were uploaded and no training occurred.

| Item | Verified evidence | Interpretation for this evaluation |
|---|---|---|
| Weights | [Pinned model card](https://huggingface.co/Yytsi/floorplan-to-3d-walls/blob/68843a3ab7b12aa03b23c36f955a0d8099b4e2ee/README.md) labels the model MIT; safe-tensor metadata records epoch 26 and author validation mIoU 0.983231 | Publisher's licence declaration and validation claim, not proof of dataset rights or accuracy on our drawings. No separate weight-specific licence file was supplied. |
| Model code | [Pinned code licence](https://github.com/Yytsi/floorplan-to-3d/blob/ccc19723d98b097b521b8289287c5143e535df0d/LICENSE) is MIT | Code licence verified separately from weights/data. |
| Training data | [CubiCasa5K licence](https://github.com/CubiCasa/CubiCasa5k/blob/master/LICENSE) is CC BY-NC 4.0 | Research evaluation only. No commercial deployment or redistribution clearance is asserted; private examples remain evaluation-only. |
| Added libraries | Licence texts in the verified wheels: SMP MIT; timm Apache-2.0 | Kept isolated, not bundled into Studio. |

A material applicability problem is visible in the [published SVG input preparation](https://github.com/Yytsi/floorplan-to-3d/blob/ccc19723d98b097b521b8289287c5143e535df0d/src/buildingcv/svg_render.py): it removes furniture, fixtures and annotations using SVG class labels before rendering. Those labels are unavailable in an arbitrary raster upload. The model card also limits outputs to floor/wall/door/window, with no furniture output. The weights do not identify an exact training-code commit, so the pinned repository's preprocessing is verified but its exact historical association with the weights cannot be independently established. This evaluation deliberately tested original raster crops; it did not remove furniture using the reference annotations or swap class IDs to improve scores.

### Same-source comparison and accuracy limits

Three real supplied examples were used: the failed coloured/hatched curved plan 16, an unseen monochrome furnished curved plan 15, and two isolated plan panels from mixed sheet 4. The saved baseline for 16 was reused without rerunning it; the existing CPU tracer was run once for each of the other two sources. The candidate used the same selected panels; plan 16 used the exact saved source pixels and crop rounding. Neither approach saw the mixed sheet's façade, title or footer as input evidence.

References were manually specified and visually checked by the assistant against original images before inspecting candidate predictions. They cover **six declared regions**, not every pixel/object in all three plans. They are not independently human-validated ground truth, and these results must be described as **provisional screening metrics**, not dataset-wide accuracy or completed acceptance. Reference JSON, hashes, original overlays, prediction masks and measurement scripts stay private. No references were used for training or prediction. Wall scoring ignores a two-pixel reference boundary band; drawn thickness/curved glazing endpoints still have annotation uncertainty.

| Source / scored regions | Existing wall precision / recall / IoU | Candidate wall precision / recall / IoU |
|---|---:|---:|
| Plan 16: curved living + upper rooms | 43.4% / 20.0% / 15.9% | **16.7% / 11.6% / 7.3%** |
| Plan 15: living, bedroom and circular drawing room | 84.8% / 81.6% / 71.1% | 82.9% / 86.3% / 73.2% |
| Mixed sheet 4: upper part of left plan | 94.0% / 68.5% / 65.6% | 90.2% / 92.5% / 84.0% |

On plan 16 the candidate increased scored false-wall pixels from **3,962 to 8,786**, and missed-wall pixels from **12,173 to 13,453**. In the lower curved-sofa reference region, wall-labelled pixels increased from **113 to 1,340**. Original overlays show hatched sofas, beds and architectural strokes labelled as windows, false openings in annotations and continued stair/furniture confusion. The broad exterior curve is partly visible in the class output but is neither correctly classified continuously nor ready for faithful extrusion.

Opening scores use one-to-one nearest opening/component matching within max(10 pixels, 2% of panel diagonal), restricted to reviewed regions. Components smaller than four pixels are ignored. Extra fragments are **prediction components, not counts of distinct physical fixtures**; this diagnostic measure is sensitive to fragmentation and does not certify opening geometry/hosts.

| Source | Candidate door matches / reference; extra components | Candidate window matches / reference; extra components |
|---|---:|---:|
| Plan 16 | 1/1; 20 extra | 5/9; 115 extra |
| Plan 15 | 0/1; 9 extra | 3/5; 9 extra |
| Sheet 4 reviewed region | 3/4; 14 extra | 0/3; 2 extra |

The existing tracer has no classified door/window output: all those typed opening references remain missed. Its untyped gap candidates are 0, 3 and 0 respectively and were not relabelled using the reference answers. The candidate frequently labels glazing as doors under its published class order. It offers no furnished-object inventory and cannot by itself supply the requested furnished model.

A common, deliberately simple enclosure diagnostic labels connected free space behind predicted wall/door/window masks, without inventing closures at gaps. Best enclosed-component IoU for the two plan-16 reference rooms is approximately 0.10/0.16 for the candidate and effectively zero for the tracer. Both approaches score zero for the sampled bedroom in plan 15 and the two sampled rooms on sheet 4. This measures enclosure recoverability, **not a trained room segmentation head**. Room topology and genuine open transitions remain unresolved; a blanket gap-closure operation would conceal these failures.

### Actual runtime, memory and correction effort

Hardware: RTX A4000, 15,352 MiB reported VRAM; Ryzen 9 5950X, 32 logical CPUs; 63.91 GiB RAM. Runtime: PyTorch 2.13.0+cu130, CUDA 13.0, SMP 0.5.0, timm 1.0.30; batch one, FP32, 512×512 letterboxed input with published ImageNet normalization. Existing model services were idle; no packages in their runtimes were changed.

- Import/model construction/weight load: **3.08 s** on the final process; the first process took **5.93 s**. The initial run exposed a one-pixel crop-rounding mismatch; final scores use the exact baseline scope. Prediction parameters/reference geometry were not tuned against the output.
- First synchronized GPU forward: **0.125 s** on the final process. Subsequent forwards: approximately **0.0085–0.0089 s per panel**. Four forwards per panel were used for timing, with identical deterministic inputs; these are model-only timings, not dashboard/import-to-model completion times. CPU crop/normalization/upload preparation took approximately **0.006–0.009 s per panel**.
- Peak PyTorch allocation **198.8 MiB**, reserved **230 MiB**. Whole-GPU usage rose from **1,172 to 1,566 MiB** while sampled with the model loaded; this approximately 394 MiB difference includes context/runtime overhead and is not an exclusive process-level peak. Peak process working set was **998.6 MiB**. It fits the actual GPU comfortably, but does not meet accuracy requirements.
- Existing wall tracer: historical plan-16 extraction **1.93 s**; new plan-15 and sheet-4 runs **2.174 s** and **0.732 s**, respectively, including current call overhead. GPU use is zero. Current CPU comparison process reached approximately **185 MiB** high-water RAM including scoring; the historical plan-16 extraction's peak RAM was not recorded.
- **No new dashboard geometry correction, furnished 3D build, or human correction-time trial was performed**, because the detector screening failed. Existing seven planting-stroke exclusions and their earlier timings remain unchanged. Preparing evaluation annotations/crop definitions is recorded in the private evaluation scripts; it is not represented as a successful in-dashboard correction session or as measured human labour. An import-to-completed-furnished-preview time remains unavailable.

### Required change of approach / next review

Do not integrate this candidate simply because it is fast. A suitable next candidate needs demonstrable raw furnished-raster input support, reliable architectural/furniture separation, explicit glazing/opening classes and local weights with traceable code/preprocessing and acceptable dataset/weight licences. The next comparison needs independently reviewed whole-plan masks/instances for coloured hatching, curves, thin glazing, stairs, furniture, junctions and genuine open transitions. Keep held-out evaluation drawings separate from any future training set. Training on these private drawings and commercial deployment remain unauthorised.

If appropriate weights do not exist, additional licensed annotations and model development are required, followed by uncertainty-aware opening-host/topology reconstruction and separate furniture recognition. No requested 3D success can honestly be shown from the tested automatic output yet. Baseline 16 remains failed; neither an upper floor nor hidden architectural detail was invented. Defaults remain explicitly assumed: 3.0 m walls and a 1.6764 m human reference, not horizontal calibration.

Review priorities: verify source-scope revision/rollback races, multi-panel transformations and preservation of existing edits; independently audit the private reference overlays and class mapping; assess a suitable raw-raster segmentation dependency before any more UI expansion. Startup/setup instructions and existing local model dependencies remain below. Normal product operation remains local; the evaluation model is deliberately not registered as a dashboard capability.

### Current verification

**Python: 336 discovered; 332 passed in the primary runtime in 50.785 s, with four SciPy pixel tests skipped there. The same four passed in the isolated SciPy runtime in 0.153 s: all 336 distinct tests exercised across both runtimes. JavaScript: all 21 suites passed.** The live browser also verified the exhausted-state control after reload; no new inference or geometry edit was initiated. Test commands: `python run_tests.py`; in a compatible SciPy runtime, `python run_tests.py test_raster_pixels.py`; run each `tests/test_*.cjs` with the configured Node runtime and project dependencies. No private real-plan fixture is in these automated tests.

## Real furnished-plan benchmark 16 — failed acceptance checkpoint

The supplied private raster (856 × 807, circular living room, two bedrooms and visible furniture) was uploaded through the isolated dashboard. The original, untouched automatic overlay, job records and intervention log are retained locally outside Git. No source-specific detection rules or geometry were injected into the saved project.

The source classifier incorrectly identified this coloured top-down drawing as a perspective/photo. The operator corrected its type, drew one plan crop, checked and saved source review: five UI gestures, **18.480 seconds** of agent interaction time including tool latency. Source approval started raster reconstruction but did not resume semantic analysis; starting Analyze plan was a separate intervention. The broader shared-scope work remains unfinished: the raster trace uses approved panels, but the semantic/OCR/structure readers do not yet consistently consume that same scope.

The preserved first automatic trace proposed **189 wall paths, 38 uncertain stretches and zero openings**, rendered as 686 typed segments in an explicitly unverified draft. At least seven proposed wall paths lie entirely within visible planting. Several fixture/furniture strokes and wall hatching also become geometry. At least six visually clear door locations were missed by the opening tracer. These are audited examples, not exhaustive precision/recall measurements. Two connected-space proposals do not establish room polygons. The planted area labelled WATERFALL does not establish an upper-floor courtyard/slab void.

The first raster job took **3.253 seconds**, including **1.93 seconds** of reported pixel processing; queue wait was **0.502 seconds**. From upload-job creation to that preview being ready was **40.164 seconds**, including source correction. The first saved browser proof was captured **63.777 seconds** after the upload interaction began; readiness and screenshot-observation times are distinct. These are not import-to-completed-model timings.

The local reader initially ran for **165.78 seconds** before an operator stop (167.301 seconds job wall-clock), retaining 53 estimates and ten pending regions. Its output included false door/fixture labels and armchairs labelled sofas. This is a partial run, not a complete detector evaluation. It was resumed through the dashboard to finish the automatic baseline; final status and corrections must be reported separately.

The next run reached its 32-call limit after **326.04 seconds** (327.420 seconds job wall-clock), saving 198 estimates with three regions still pending and 151 review issues. During that run, seven independently checked planting strokes were excluded through the dashboard. This marks the semantic result stale against the revised drawing, as expected; it must not be imported as current reviewed evidence. A further dashboard resume was requested for the remaining regions against the saved corrections.

That final resume took **66.21 seconds** (67.338 seconds job wall-clock, six model calls). It exhausted the queue but **did not achieve complete coverage**: a dense region was still saturated at the maximum subdivision depth. Final output: 233 estimates, 179 review issues, 19 completed and seven saturated passes, zero queued or failed regions. One saturated pass is at depth two. Merely resuming the same cached jobs cannot recover the missing records. The UI still offers Resume analysis; the final report also remains stale, so it is not eligible for uncritical import. Source/revision lifecycle and this saturated-region recovery path require attention in addition to detector accuracy. There is still a circular-seating/curved-wall conflict and no reviewed door/window topology.

Across the three reader runs, reported local model-processing time totals **558.03 seconds** (9 min 18 s); corresponding job wall-clock totals **562.06 seconds**. The observed upload-to-incomplete-checkpoint elapsed time was **958.169 seconds** (15 min 58 s), including inspection, interaction, tool latency, pauses and report work. Neither value is a completed-model turnaround time. Measured source correction plus geometry correction totals **83.231 seconds** of agent interaction; human hands-on time is unavailable. The initial Analyze, Stop and first Resume actions have recorded timestamps but were not separately duration-timed, so the intervention timing record is not exhaustive. The last Resume was timed at 0.672 seconds; reopening was timed at 0.163 seconds for navigation only, with persistence verified afterward. These measurement limits must not be hidden.

Manual geometry changes so far are **only seven rejected planting strokes**, in five saves. No candidate was blanket-approved, moved or straightened; the living-room curve and sofas were not edited. The saves took **28.543, 31.221, 1.722, 1.673 and 1.592 seconds**, respectively (**64.751 seconds** total measured agent interaction time, 18 gestures). The first save excluded three verified selections; four attempted Ctrl-clicks missed tiny strokes. The second single-path save included a missed coordinate click and a zoom. The last three saves each selected and excluded one path. Exact IDs and timestamps are in the private intervention log. Reopening the dashboard verified all seven exclusions persisted, pending paths decreased from 227 to 220, and the partial draft decreased from 686 to 657 typed segments. This is a saved/reopened **partial correction**, not the requested corrected furnished model. Human correction time has not been measured.

The user chose the existing project defaults instead of supplying a measured dimension: **3.0 m wall height and 1.6764 m / 5.5 ft human reference**. These are assumptions, not measurements or sufficient evidence for horizontal scale. The current unfurnished draft falls back to a 10 m sheet width; it is explicitly uncalibrated. Do not infer an upper storey from the stair, hidden walls, unseen furniture or a courtyard void. A corrected furnished 3D scene has **not** been completed, saved and reopened for this sample. The unseen monochrome furnished-plan follow-up remains pending until this first acceptance case passes.

Hardware: AMD Ryzen 9 5950X (16 cores), approximately 64 GB RAM, NVIDIA RTX A4000 (15,352 MiB reported VRAM); local Ollama 0.35.0, `qwen3-vl:8b-instruct`, 8.8B Q4_K_M. The boundary extractor remains the deterministic original-pixel threshold, distance-transform/stroke-width mask, connected components, skeleton graph and bounded-error line/arc/spline fitter. There is no trained architectural segmentation component installed. Merely adding review controls or changing the vision prompt cannot establish reliable wall/furniture separation. The next reconstruction approach must produce class-labelled wall, glazing and opening masks, retain original-pixel evidence and uncertain boundaries, then solve opening hosts and room topology. It needs verified local weights/runtime and licensed, reviewed held-out annotations; private examples are evaluation data, not implicitly authorised training data. The research dependency and licensing limitations below still apply.

No application code or test suite was changed for this benchmark run. Prior automated test results below must not be presented as new runs or as evidence that this real plan passed. The unseen monochrome test was deliberately not started: the user requested it after completing this case, and the first real-plan acceptance criterion has not been met. There is no finished corrected furnished-model screenshot to present; local proof shows the original automatic boundary overlay and the saved/reopened partial draft after the seven exclusions.

## Follow-up milestone after d5337c2 — 1 October 2026

This is a tested **partial milestone**, not a claim that the supplied real raster plans now reconstruct accurately. The earlier evaluation below is retained as the baseline. Source rejection, crop correction, grouped review and responsiveness were exercised in an isolated local dashboard; the original running Studio and saved client edits were not restarted or replaced.

### Implemented and verified

- Curve validation now requires native arc/Bezier or accepted raster arc/spline provenance, continuous curved samples, and an explicit observation-to-source link made in the dashboard. Geometry and observation fingerprints invalidate that link after edits. Bounding-box locality is only a rejection check, never identity. The exact 100×100 `L-wall` reproduction stays unresolved; a straight L, unbound unrelated curve and changed linked geometry cannot clear the observation. Curve linking and its undo are under boundary review. This is reviewed correspondence, not automatic semantic matching from a box.
- Original-image source triage runs before raster preparation/tracing. It uses CPU whiteness/chroma, long orthogonal strokes and whitespace bands. Mixed/uncertain sheets require reviewed plan crops. Crop rectangles mask evidence; they never become walls. The dashboard supports drawing/removing crops, source-type correction and undo. Old candidates become inactive when their source scope no longer matches, while saved drawing edits remain intact.
- Adjacent collinear wall paths can be selected as one connected run; Control/Command-click also selects individual paths. Keep/exclude/defer is atomic and undoable. Endpoint/tangent tests do not bridge doorway gaps. Openings and uncertain exterior contours retain individual review; completeness checks and estimate acknowledgement remain mandatory.
- A single bounded CPU lane handles plan setup and raster reconstruction independently of the serialized model lane. Tracing numerical-library threads are capped at two, with a RAM guard. Duplicate worker startup is suppressed. Plan-setup commits no longer replace the entire live database, preserving concurrent job changes. Review/export endpoints copy a read-only snapshot under the lock and do expensive geometry work afterward. Endpoint indexing replaces quadratic segment deduplication; per-request caches remove repeat architecture/validation work.
- Dashboard testing found and fixed an area-editor crash when a newly added section briefly had no calculated percentages. No approval or reconstruction checks were removed.

### Actual dashboard demonstrations

| Example | Result at this checkpoint |
| --- | --- |
| Supplied perspective negative case | Classified `perspective_or_photo`; no plan panels, no active wall draft and **zero typed segments**. Its previous erroneous report remains preserved but inactive. |
| Supplied mixed presentation sheet | Classified mixed and blocked from tracing until crop review. Automatic proposal was one broad band, not a correct final split. Two dashboard-corrected plan regions exclude the facade and footer. Retrace produced 27 wall paths, 32 uncertain stretches and 53 typed segments; geometry remains partial/unverified. This demonstrates assisted isolation, not fully automatic panel segmentation. |
| Independent clear raster control | Synthetic 400×400 single closed room with a thin chair symbol, intentionally no openings. One wall path/eight spans; thin chair outline was not extruded. Three unsupported semantic conflicts were rejected individually. A floor/section was outlined and a chair positioned/saved through the dashboard; geometry review completed and the shared scene retained the chair after reopening. Scale/product dimensions remain estimates; no image-generation approval was asserted. |
| Supplied real furnished/curved plans | Still incomplete. No supplied real raster plan reached an accurately reviewed, fully furnished 3D reconstruction in this milestone. The synthetic control must not be substituted for that acceptance criterion. |

Private screenshots show the actual source overlays, negative case and furnished control. They stay local with the evaluation data. No supplied source, crop, overlay, CAD file, model or private report is in Git.

Correction timing was measured as agent browser wall-clock, including tool/inspection latency: the successful two-crop operation took **19.417 s**; including an initial misplaced crop and undo, **96.936 s**. The control's room/furniture/save/review sequence took **152.206 s** after the area-editor fix; total control review including debugging was **519.301 s**. These are not measured human hands-on times or a usability benchmark. A timed human review and a real furnished-plan completion remain required.

### Responsiveness evidence

The baseline local reader occupied the old single queue for roughly 565–584 seconds; that delayed lightweight preparation, rather than indicating nine minutes of pixel tracing. A regression now holds the model lane blocked while CPU preparation completes within two seconds and asserts one owner per lane. This does not accelerate model inference itself or establish cross-process GPU exclusion against unrelated applications.

On the same saved curved sample, three final localhost structure-review requests took **0.615, 0.478 and 0.456 seconds**. The previous dashboard observation was approximately 8.34 seconds under queued analysis, so load conditions differ. Profiling separately fell from 7.320 to 1.311 seconds after indexing/caching; profiling timings must not be confused with HTTP latency. Long review computations no longer hold the editing lock; snapshot copying still scales with database size.

### Segmentation dependency and remaining failures

The active wall extractor is still SciPy/NumPy/Pillow masks, skeletons and line/arc/spline fits. No trained architecture/furniture segmenter was installed or evaluated against annotated examples. Thick furniture, thin glazing, junctions, opening hosts, non-Latin labels and room topology remain failure cases. Source triage is a conservative heuristic, not a general perspective detector: sparse monochrome perspectives or facade drawings can resemble plans. Legacy reports without source-review metadata require a recheck; the new guard runs on preparation/reconstruction rather than rewriting existing projects on startup.

[CubiCasa5K](https://github.com/CubiCasa/CubiCasa5k) is a locally runnable research candidate for multi-class floor-plan segmentation, but its documented environment is old (Python 3.6/PyTorch 1.0). Its [licence](https://github.com/CubiCasa/CubiCasa5k/blob/master/LICENSE) is CC BY-NC 4.0, so it cannot be silently bundled as an unrestricted commercial dependency. Evaluation needs a compatible isolated runtime, verified pretrained weights/checksum and reviewed held-out masks for walls, furniture, openings and panels. Download size/checksum have not been verified; the dashboard reports the missing dependency rather than offering an unverified installer. No weight/dataset download or training use of supplied examples was performed. A different suitably licensed model may be necessary.

### Tests and next review targets

- Python: 322 discovered; 318 passed in the primary runtime and four SciPy-dependent pixel tests skipped there. Those same four passed in the installed SciPy runtime: **all 322 exercised across the two runtimes**, not 326 distinct tests.
- JavaScript: all 20 suites passed; browser-script syntax checks passed. Actual crop correction/undo, connected-run selection, individual conflict rejection, section creation, furniture persistence and boundary completion were tested through the dashboard.
- Regression additions cover the exact curve false positive, binding invalidation, source gates/scope changes, crop masks, atomic group undo, GPU/CPU lane ownership and endpoint-index tolerance.

Review `curve_review.py` for provenance/correspondence; `source_panels.py` for false plan classifications and safe crop scope; `wall_runs.py` for grouping; `engine.py`, `plan_setup.py` and snapshot endpoints for concurrency. Priority gaps remain a licensed local segmentation benchmark, real-plan furnished completion, human correction timing and automatic floor registration. DWG conversion remains a separate unsupported capability. Existing startup instructions and model limitations below still apply.

## Scope and publication boundary

This is the complete reviewable application source, UI, workflows and tests, not a runnable bundle containing models or client projects. It is a fresh Git root snapshot of the tested local checkpoint `01b123d`, with publication-specific sanitization. The private local commits are not ancestors of this branch. The original working installation, commits and client files were preserved unchanged.

Excluded: client floor plans and detections, screenshots, generated media, project databases, credentials, private configuration, machine-specific import scripts, model weights, bundled runtimes, caches and logs. Public fixtures are generated synthetic shapes or generic test data. One private-plan conflict regression was replaced with an independent synthetic fixture covering the same six conflict cases. No client geometry was copied into that fixture.

## Completed work

- Upload / Review & 3D / Images & Video navigation in the existing dashboard.
- Original-preserving image preparation; native PDF/DXF path, layer, entity and transform metadata; explicit unsupported-DWG messaging.
- Local original-pixel wall masks, skeleton paths, line/arc/spline fitting, uncertain exterior contours, opening candidates and connected-space proposals.
- Source overlays with focused point corrections, opening classification, saved revisions and undo/redo; synchronized partial 3D. Native geometry previews no longer wait for room recognition.
- Preserved curved architecture, polygon floors and voids where supported geometry exists; GLB and structured scene/provenance export.
- Checkpointed local semantic analysis, original/enhanced disagreement and conflicting-label review. Detection rectangles never become walls.
- Dashboard setup/readiness, installed-service startup, local-only endpoints, memory guards, serialized heavy jobs, cancellation, retry and ambiguous-submission recovery.
- Explicitly approved, resumable downloads with pinned size/hash/licence. Current catalogue covers one FLUX diffusion weight only.
- Existing furniture/material references, camera controls, local FLUX image generation, image approval, LTX video generation, playback and export retained.
- Scene fingerprints invalidate approvals after geometry changes. Design-light proxies are separate from observations; no detected lights does not prove no lighting exists.

## Current detection and 3D limitations

### Review fixes in this revision

1. **Raster completion:** added persisted, revision-bound boundary review with actionable checks and explicit acknowledgement. Pending, deferred, edited-but-unconfirmed paths, unhosted openings, invalid/overlapping section polygons, missing floor outlines and semantic conflicts prevent completion. Open transitions do not become invented walls. Changes to source, geometry, floors, scale or semantic evidence revoke completion. Image-generation checks consume this state instead of permanently rejecting every raster plan.
2. **Rescan identity:** candidate IDs bind source hash, analysis coordinates and geometry rather than array positions. Corrections and drawing edits transfer only for exact one-to-one evidence matches. Changed or ambiguous matches are archived for review, and rescan invalidates stale undo/redo. Legacy sequential IDs cannot classify unrelated new openings.
3. **Shared scene:** sections select the shared furnished scene by default even when raster evidence exists. A separate Boundary draft checkbox exposes the incomplete diagnostic view. GLB export follows the selected scene; regression checks confirm a chair remains in the shared scene/export.
4. **Curves:** generation checks match each curved-wall observation to corresponding supported curved geometry. A matching accepted curve clears that particular issue; straight, unrelated and unresolved curves remain blocked.
5. **Product test and execution:** the sanitized embedded-data fixture now uses the supported retailer domain with synthetic product values. A negative test preserves rejection of unsupported domains. The test runner prevents accidental execution against a different installed checkout.

Regression coverage includes save rollback, stale review requests, correction migration, duplicate candidates, reordered/reversed paths, source/analysis changes, export selection and per-observation curve matching. These fixes improve reviewability and state safety; they do not turn the pixel tracer into a semantic segmentation model.

The raster tracer is deterministic SciPy/NumPy/Pillow processing, not trained architectural segmentation. It recovers supported strokes but can confuse thick furniture outlines with walls and miss thin glazing or doorways. Exterior classification, opening hosts, junctions and complete room topology remain provisional. Open-plan spaces are not forcibly enclosed. Connected free space is not automatically a confirmed room or slab.

A partial 3D preview is explicitly unverified. Boundary-only diagnostics remain available, while plans with sections use the shared furnished scene by default. An explicit geometry-review completion lifecycle now checks candidates, opening hosts, curves, floor/section polygons and conflicts. It requires a source-completeness check and acknowledgement of estimated dimensions; this is user review, not proof of reconstruction accuracy. Changes invalidate completion. Specialist editors still exist under Advanced. DWG has no validated compatible local adapter.

FLUX reference-latent conditioning is soft. Depth, normal, object-ID and edge guides are exported, but no validated geometry-control model enforces them. A local synthetic render test invented openings and failed architectural review. The image and derived video were rejected after a test-only LTX approval was removed. Attractive media and completed jobs do not establish reconstruction accuracy.

There is no annotated held-out accuracy benchmark. No precision/recall, wall error or room-IoU claim is made. Trained local architecture segmentation plus reviewed masks, curves, opening relationships and room topology are still needed. Automatic proposed-lighting layouts and separate-sheet registration are unfinished.

## Actual test results

Correction to the first handoff: the claimed final 36-test sanitization rerun imported another installed checkout through an embedded Python search path. That claim was invalid. The external reviewer correctly reproduced the public snapshot's product-fixture failure. The checkout-anchored `run_tests.py` now verifies the imported application path before discovery. Current results below supersede the initial publication claims:

| Test | Actual result |
| --- | --- |
| Python suite, anchored to this checkout | 312 discovered in 31.227 s: 309 passed, 3 skipped because that runtime lacks SciPy |
| Those 3 pixel tests, installed SciPy runtime | 3 passed in 0.083 s; all 312 tests exercised across the two appropriate runtimes |
| JavaScript | All 20 `tests/test_*.cjs` suites passed; modified browser files passed syntax checks |
| Product fixture | Supported retailer domain restored around synthetic product data; unsupported-domain rejection retained; production domain restriction unchanged |
| Earlier installed-app dashboard journey | DXF upload, native preview, original-byte preservation, GLB export, point correction/undo and opening defer/undo passed |
| Earlier local media execution | FLUX ~45 s; LTX 5-second clip ~481 s; playback and export passed at 1920×1080, 24 fps, 120 frames |
| Media fidelity | Failed architectural review; invented openings were recorded and outputs rejected |

The installed-app UI/media results predate publication sanitization. No fresh model render or cloud inference was required for publication. Private screenshots and logs are deliberately omitted. Test duration is machine-dependent; tests are not an accuracy benchmark.

### Local dashboard evaluation, 1 October 2026

The supplied archive's 27 JPEGs and two architectural DWG examples from the [official Autodesk sample page](https://www.autodesk.com/support/technical/article/caas/tsarticles/ts/6XGQklp3ZcBFqljLPjrnQ9.html) were retained outside this repository, with a local hash manifest. They are evaluation examples, not training data. No source images, CAD files, overlays, detection reports or private project records are published. Four representative archive entries were uploaded through a separate loopback dashboard and inspected in its split review workspace; the existing working Studio and client projects were preserved.

| Private evaluation example | Original-pixel proposals | Actual dashboard result |
| --- | --- | --- |
| Curved furnished plan, 1200×2027 | 144 wall paths, 44 uncertain stretches, 2 openings, 2 connected spaces; extraction 4.009 s | Exterior curve retained as uncertain contour. Some furniture and fixture edges become wall candidates; thin glazing and many openings are missing. Local reader saved 316 estimates after 565.18 s with incomplete coverage and label conflicts. OCR supplied four unreliable sections with no floor assignment. Geometry review correctly remains incomplete. |
| Low-resolution two-floor plan, 467×906 | 59 wall paths, 40 uncertain stretches, 8 openings, 1 connected space; extraction 0.786 s | Original/enhanced toggle works. Several curved and straight boundaries are visible, but the page border is also proposed. Floors are not registered or stacked; OCR finds no reliable sections. Local reader saved 173 estimates after 584.24 s, with six regions still pending and a resumable checkpoint. Partial 3D remains unverified. |
| Mixed facade and three-plan presentation sheet, 896×1200 | 268 wall paths, 42 uncertain stretches, 0 openings, 4 connected spaces; extraction 6.728 s | **Failure:** facade, vegetation and sheet edges are extruded alongside plan strokes. No automatic panel isolation or reliable section assignment. Queued semantic analysis was cancelled through the dashboard after this failure was recorded; its semantic accuracy was not evaluated. |
| Perspective interior negative control, 1200×1607 | 358 wall paths, 96 uncertain stretches, 6 openings, 1 connected space; extraction 8.322 s | **Failure:** source-type rejection is missing, producing a meaningless partial 3D draft from a non-plan image. Completion remains blocked. Queued semantic analysis was cancelled through the dashboard; cancellation retained the source and proposals. |
| Autodesk architectural example, imperial DWG | No native geometry extracted | Dashboard rejected the file with an explicit unsupported-DWG message and offered DXF/PDF. No compatible local DWG reader/converter was found. This is a capability failure, not a successful CAD reconstruction. |
| Autodesk architectural annotation/scaling DWG | No native geometry extracted | Same explicit rejection; original bytes retained locally. No conversion or cloud fallback attempted. |
| Independently generated DXF control | Declared metre units, line/arc geometry, layers and transformed block metadata retained; 132 typed preview segments | Curved wall and window visible in partial 3D; dashboard GLB export downloaded successfully. Symbol metadata is retained, but a generic imported furniture block is not automatically a detailed 3D furniture asset. This control is not a converted Autodesk sample. |

Pixel extraction timings are worker timings, excluding queue wait, OCR, semantic reading and review rendering. The single job queue delayed later CPU tasks behind the first visual-reader run by roughly nine minutes. The low-resolution job also encountered review-lock contention. A full 3D reconstruction has **not** succeeded on these supplied raster examples; candidate counts are not precision or recall.

The real dashboard tests also exposed and fixed an isolated-Python worker import failure, repeated whole-report hashing during correction lookup, and a stale refresh race after undo/redo. The failed worker run was retained in Activity and retried successfully. Source-bound defer, undo and redo persisted; the UI reported both views updated. Diagnostic-only mode produced a separate partial draft while the normal mode used the shared scene. A chair was explicitly added as test furniture, saved without approving the geometry, retained after reopening, and found by stable ID in the dashboard-exported furnished GLB (305,672 bytes). The native control exported a valid GLB 2.0 file (100,888 bytes). All five imported original asset hashes matched their stored originals. Completion stayed disabled for the real plans. The complete validation lifecycle was exercised with synthetic automated regressions, not by falsely approving incomplete real plans.

Remaining priorities are source/panel classification before tracing, trained local architecture-versus-furniture segmentation, opening/junction relationships, floor registration, non-Latin room labels, topology, and large-report responsiveness. Review response time on the curved sample was still about 8.34 s during queued local analysis after removing redundant hashing. The raster method has not been replaced by another vision prompt. A locally runnable trained segmenter plus licensed, reviewed annotations for walls, glazing, openings, symbols and mixed-sheet panels is a concrete missing dependency. These private samples have not been annotated or approved for training.

### Publication checks

All 203 files in the current staged snapshot were inspected with a local pattern scanner for credential formats, credential assignments, authenticated URLs, private filesystem paths, client identifiers and excluded file types. The public gazetteer was decompressed for inspection; the sole PNG is the UI logo and has no embedded metadata. The only retained credential-shaped strings are deliberately invalid dummy URLs in rejection tests. No sensitive-content findings remained. This is a pattern scan and manual review, not a guarantee of exhaustive secret detection.

Both original private local commits were inspected and kept private. The publication branch starts with a clean parentless snapshot; this revision follows only that sanitized public history, whose reachable file contents are scanned again before pushing. Local samples, test logs and audit manifests remain outside this repository.

### Test commands

After the developer dependencies in SOURCE_SETUP.md are installed, from the repository root:

```powershell
python run_tests.py
Get-ChildItem tests -Filter 'test_*.cjs' | ForEach-Object {
  node $_.FullName
  if ($LASTEXITCODE -ne 0) { throw "Test failed: $($_.Name)" }
}
python run_tests.py test_raster_pixels.py
```

Use the Python runtime with SciPy for the pixel tests. `PIXELOID_NODE` can select an existing Node executable; otherwise Node is resolved from the bundled path or PATH. Do not execute fixture-export `.cjs` files as test suites: they print large geometry JSON.

## Local startup and dependencies

See [SOURCE_SETUP.md](SOURCE_SETUP.md). The source checkout needs Python, Node/sharp and the libraries in `requirements.txt`. The local application was tested with Python 3.13.14 on Windows and an RTX A4000 with about 15 GB VRAM / 64 GB RAM. This does not certify other hardware.

The dashboard can start configured local ComfyUI and Ollama services and verifies their readiness. The fresh-machine installer is incomplete. Runtime paths belong in ignored `studio.local.json`; `studio.example.json` contains no credentials or machine-specific paths. Core inference must remain local; approved dependency downloads are distinct from project processing.

Missing from this repository by design: ComfyUI/PyTorch, Ollama and visual-reader weights, FLUX/LTX encoders and VAEs, optional Real-ESRGAN/Spandrel, all model binaries. Required filenames are listed in SOURCE_SETUP.md and the workflow templates. Missing capability must produce an actionable dashboard limitation, never cloud fallback.

## Specific areas needing external review

1. **Reconstruction correctness:** `raster_geometry.py`, `raster_reconstruction.py`, `drawing_scene.py`, `curve_geometry.py`. Review masks, curve tolerance, false furniture walls, opening host cuts, junction topology and uncertainty propagation. Propose measurable improvements and a concrete local segmentation/data dependency.
2. **Shared state and preservation:** `scene_document.py`, `scene_control.py`, `store.py`, `detection_review.py`, `plan_health.py`. Review stable identities, concurrent edits, cache invalidation, undo rollback, approval invalidation and migration compatibility. The scene document is an additive projection; multiple legacy editable records remain authoritative.
3. **Local job safety:** `engine.py`, `job_control.py`, `standalone.py`, `local_setup.py`, `component_setup.py`, `vision_study.py`. Check model residency, cancellation ownership, restart recovery, duplicate submissions, partial downloads, licence consent and memory limits. Headroom thresholds are not model-specific peak-memory predictions.
4. **Image fidelity:** `geometry_guidance.py`, `shared_floor.py`, `templates/flux.json`, `templates/ltx.json`. Recommend compatible local structural conditioning and verification, not repeated prompt changes as a geometry substitute.
5. **UI integration:** `static/structure-check.js`, `static/raster-review.js`, `static/plan-workspace.js`, `static/local-setup.js`. Reduce specialist-editor fragmentation, make incomplete rooms actionable, preserve view/selection and review accessibility/error states.
6. **Security and packaging:** `server.py`, `web_image.py`, `products.py`, download handling and setup. The server is loopback-only, not authenticated for public hosting. Do not expose it through a tunnel. Assess source installation reproducibility, licences and clean-repository exclusions.

Please separate verified defects from hypotheses, cite files/lines, preserve existing user corrections, and propose small testable changes. Do not infer that missing client examples, binaries or private history should be added to this public repository.
