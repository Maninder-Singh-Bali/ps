# Source-review setup

This repository contains source, not a bundled distribution. These are one-time developer/reviewer instructions; normal installed-app operation belongs in the dashboard. Windows is the tested platform (including Windows OCR and guarded process discovery).

## Dashboard and tests

Use Python 3.13 and Node.js from their official distributions. Install the reviewed dependencies in an isolated environment; this step uses the internet and downloads packages:

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
npm install
Copy-Item studio.example.json studio.local.json
python server.py --port 8860 --data .\data\review
```

Open http://127.0.0.1:8860/. Choose another unused port if necessary; never stop an existing Studio merely to run this review copy. All files in `data/` and private configuration are ignored by Git. No example includes a user's filesystem paths.

The repository-root `node_modules/sharp` installed by npm is resolved by the drawing renderer. Node must be on PATH, or selected with the local `PIXELOID_NODE` environment variable. Portable Node selection was added to the mesh test; existing NODE_PATH entries are preserved by drawing export. The supplied Windows launcher is intended for the installed distribution's `runtime/python/pythonw.exe`; a plain Git clone does not contain that executable.

`run_review.py` optionally seeds an independently synthetic curve/void example in a separate ignored review database. It binds port 8789 and must only be used if that port is free. It contains no client plan. Synthetic fixtures do not establish real-plan accuracy.

## Local models and services

For developer checks, run `python run_tests.py` from this checkout, then the `tests/test_*.cjs` suites with Node. The Python runner anchors imports to this source tree so an embedded runtime cannot silently test a different installed copy. Use `python run_tests.py test_raster_pixels.py` with the configured SciPy runtime for pixel tests. See REVIEW_HANDOFF.md for actual results and limitations.

Open **Setup** in the dashboard. For an existing installation, connect its local engine Python and ComfyUI folder, then use Start renderer / Start reader. Do not commit the resulting `studio.local.json`. Blank fields in the example are intentional; no guessed machine path is included. A separate SciPy Python can be configured with `geometry_python` if the dashboard Python lacks SciPy.

Required ComfyUI workflow files are `templates/flux.json` and `templates/ltx.json`. The current templates expect these local filenames:

| Model directory | Filename |
| --- | --- |
| text_encoders | `qwen_3_4b.safetensors` |
| text_encoders | `gemma4-12b-with-proj-ltx-2.5-comfy-int8-convrot.safetensors` |
| diffusion_models | `flux-2-klein-4b-fp8.safetensors` |
| diffusion_models | `ltx-2.5-22b-distilled-transformer-comfy-int8-convrot.safetensors` |
| vae | `flux2-vae.safetensors` |
| vae | `ltx-2.5-audio-vae-bf16.safetensors` |
| vae | `ltx-2.5-video-vae-bf16.safetensors` |

The tested reader was `qwen3-vl:8b-instruct` in local Ollama. Optional plan upscaling uses `realesr-general-x4v3.pth` with a compatible Spandrel/Torch runtime; see model-notes. These are requirements, not a claim that all distributions are compatible or freely redistributable. Review each provider's current licence, hardware and storage requirements before downloading. No model licence acceptance or automatic model download happens on clone/import.

Only one pinned FLUX diffusion-weight download is currently offered in Setup, with size/licence/hash and explicit consent. The complete fresh-machine installer, a trained architectural segmentation component and a validated DWG adapter remain missing. PDF, DXF and supported images remain available; missing models must be reported in the dashboard.

Owned renderer startup disables cloud API/custom nodes and sets offline model-library flags. Shared existing local services are reused rather than reconfigured. Their extensions and network settings remain the owner's responsibility. Never supply remote inference endpoints or public tunnels. A source-review installation should use synthetic fixtures and its own ignored data directory.

## Recovery and limitations

Job state and inputs are persisted locally. Activity offers Cancel, Retry or Recover; ambiguous render submissions are checked against local history before resubmission. Keep a backup of private projects before testing code changes. Never point this review copy at another running Studio's database.

See REVIEW_HANDOFF.md for exact tests, measured outcomes and unresolved accuracy limits. See PIXELOID_STUDIO_PROTOCOLS.md for interpretation and preservation rules. Dependency manifests record the versions exercised locally; installing this exact set on a fresh machine has not been independently certified.
