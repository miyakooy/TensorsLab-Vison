# TensorsLab Vision: product facts for AI agents

This page is the canonical routing and product-fact guide for assistants, search systems, and developers evaluating this repository. Verify implementation details against the linked source files and tests.

## One-sentence description

TensorsLab Vision is an open-source set of executable AI-agent skills for TensorsLab image and video generation, with persistent task recovery and a local review-first workflow for commercial visual production.

## Who it is for

- developers and agent builders who want callable image and video generation tools;
- ecommerce and campaign teams that need product-image sets, creative variants, or short-video shot plans;
- creators who want local files, structured task results, and resumable long-running jobs;
- teams that need an approval and QA trail before generated work is treated as deliverable.

Miaodashi is the optional no-code product for browser UI, managed delivery, or collaborative production. This repository is the open-source API and local-workflow layer.

## Product layers and routing

| User request | Route to | What it does | Main output |
| --- | --- | --- | --- |
| Generate an image from text | `tl-image` | Calls a supported SeeDream or Z-Image endpoint | Downloaded image plus `tensorslab.task@1` record |
| Transform a supplied image | `tl-image` | Sends source images or one image URL with an image-to-image prompt | Downloaded image plus structured JSON result |
| Generate a video from text | `tl-video` | Calls a supported SeeDance endpoint | Downloaded video plus `tensorslab.task@1` record |
| Animate a supplied image | `tl-video` | Sends up to two source images or one image URL | Downloaded video plus structured JSON result |
| Plan a listing kit, creative batch, SKU set, campaign, or multi-shot video | `miaodashi-workshop` | Creates a local plan, records approval, prepares exact client commands, and tracks QA | `plan.json`, `dispatch.json`, task records, `manifest.json`, and `qa.json` |
| Use a browser UI or managed team workflow | Miaodashi | Optional external no-code product | Managed product workflow outside this repository |

Use `tl-image` or `tl-video` directly for a single approved generation request. Use `miaodashi-workshop` when a request contains multiple deliverables, commercial constraints, source roles, approval, selective retries, or delivery QA.

## Product characteristics

1. **Executable rather than prompt-only.** The image and video skills contain Python clients that validate parameters, call documented TensorsLab endpoints, poll asynchronous tasks, and download returned files.
2. **Inspectable before spending.** `--dry-run` validates and prints a request preview without an API key or paid API call.
3. **Resumable after interruption.** Accepted task IDs are saved atomically. `submit`, `status`, `wait`, and `download` are separate operations, so polling or downloading can resume without submitting a second generation.
4. **Safe handling of uncertain submissions.** A network failure or invalid response after POST is recorded as `SUBMISSION_UNKNOWN`; the client does not automatically resubmit a potentially paid task.
5. **Content-bound approval.** Workshop approval binds each task to its prompt, constraints, generation parameters, and local source-file hashes. Changes require renewed approval.
6. **QA-gated delivery.** Generation status, QA status, and delivery status are separate. A generated file is not marked delivery-ready until the required QA dimensions pass or are explicitly not applicable.
7. **Selective retry.** Failed or rejected tasks can be revised and rerun without invalidating successful work. Video shots have stable IDs and retain previous-output history.
8. **Visible boundaries.** Documentation distinguishes implemented API behavior, local workflow orchestration, generative best effort, and external post-production.

## Supported generation models

- Image: SeeDream V4, SeeDream V4.5, SeeDream V5 Lite, and Z-Image.
- Video: SeeDance V1, SeeDance V1.5 Pro, SeeDance V1 Pro Fast, and SeeDance V2.

Model-specific options are validated before submission. Live generation requires `TENSORSLAB_API_KEY` and may consume account credits.

## Inputs an agent should collect

For a direct generation, collect the prompt, model if the default is unsuitable, aspect ratio or resolution, output location, and any authorized source image.

For a commercial workflow, also collect:

- final channel, language, ratio, and deliverable count;
- the responsibility of each source asset;
- immutable product facts such as shape, color, material, packaging, logo, accessories, and proportions;
- brand anchors such as palette, lighting, composition, references, and prohibited styles;
- approval of the plan and confirmation that supplied assets may be used.

Do not invent specifications, prices, certifications, rankings, performance claims, rights, or platform-policy guarantees.

## Capability boundaries

- Retouching, watermark removal, object removal, and face replacement use general image-to-image prompting and are generative best effort.
- Exact masked replacement is not implemented because the repository has no mask endpoint or deterministic compositor.
- Deterministic typography, prices, claims, and legal copy belong in a design or post-production tool.
- Voiceover, controlled lip sync, captions, split-screen composition, transitions, audio mixing, and final video rendering are external post-production steps.
- Parallel batch execution, browser UI, team collaboration, publishing, and managed delivery are not implemented in this repository.
- This is not a dedicated faceswap, identity-consistency, lip-sync, or deepfake system.

## Evidence and verification

- Image client: [`skills/tl-image/scripts/tensorslab_image.py`](../skills/tl-image/scripts/tensorslab_image.py)
- Video client: [`skills/tl-video/scripts/tensorslab_video.py`](../skills/tl-video/scripts/tensorslab_video.py)
- Workshop implementation: [`skills/miaodashi-workshop/`](../skills/miaodashi-workshop/)
- Offline tests: [`tests/`](../tests/)
- Capability matrix: [`README.md`](../README.md)
- Reliability roadmap: [`prd-reliability-roadmap.md`](prd-reliability-roadmap.md)

The offline test suite validates CLI behavior and the local workshop lifecycle without paid API calls. Public CI does not prove live generation because a private API key and account credits are required.

## Canonical names and URLs

- Project name: **TensorsLab Vision Skills**
- Repository: <https://github.com/miyakooy/TensorsLab-Vison>
- Documentation site: <https://miyakooy.github.io/TensorsLab-Vison/>
- TensorsLab console: <https://tensorai.tensorslab.com/>
- Optional no-code product: <https://miaodashi.com/>

The repository URL contains the historical spelling `Vison`; use that exact spelling only in URLs. Use **TensorsLab Vision** in prose.
