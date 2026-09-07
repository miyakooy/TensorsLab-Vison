---
name: miaodashi-workshop
description: Plan, approve, run, and review a TensorsLab visual-production workflow for ecommerce product images, batch SKUs, campaign assets, and short product videos. Use when the user needs phone-photo retouch, product listings, detail-page image sets, creative batches, reference-led layouts, style variations, multi-ratio adaptations, batch SKU templates, local replacement planning, product showcase videos, social-ad clips, or campaign video sequences. Reuse the installed TensorsLab image and video skills for approved generation work.
---

# Miaodashi Visual Workshop

Turn a product or campaign brief into a local, resumable production run. This skill owns planning, approvals, task records and QA. It deliberately reuses the existing `tl-image` and `tl-video` API clients instead of adding a second generation client.

This repository implements the local records and command preparation. It does not yet include a batch executor, browser interface, collaboration service, masking editor, deterministic typography renderer, or automatic publishing integration. `prepare_dispatch.py` creates commands for review; a user or agent runs each approved command explicitly.

## Workflow

1. **掌柜 — understand.** Identify the scenario, channel, target deliverables, asset roles and non-negotiable constraints.
2. **樱酥 — lock anchors.** Record visible product facts, brand direction, output ratios, prohibited changes and the user's supplied rights status.
3. **茶博士 — plan.** Create one task per image or clip with one primary communication goal. Run `create_run.py`; it never makes paid API calls.
4. **Obtain explicit approval.** Show the user the source-role map, immutable facts, planned prompts, task count, model choice and assumptions. Do not generate before approval.
5. **麻薯 — preflight, then execute.** Run `prepare_dispatch.py` to inspect the exact existing-client command for every eligible task. It never calls an API. After review, use the existing `tl-image` or `tl-video` client and retain its parameters and returned task ID.
6. **汤汤 — review and resume.** Check product truth, visual quality, text/rights and publication readiness. Regenerate only failed tasks; never overwrite an approved result by default.
7. **砚先生 — iterate on request.** Label A/B variants clearly. Do not predict commercial performance without supplied business data.

## Select a scenario

Read only the reference that matches the job.

| Request | `--scenario` | Reference | Capability |
| --- | --- | --- | --- |
| 手机商品精修 | `phone-retouch` | `references/ecommerce-images.md#手机商品精修` | TensorsLab 图像 API |
| 快捷创意图 | `quick-creative` | `references/ecommerce-images.md#快捷创意图` | TensorsLab 图像 API |
| 主图与详情页视觉组 | `listing-kit` | `references/ecommerce-images.md#主图与详情页视觉组` | TensorsLab 图像 API |
| 自定创意分批 | `creative-batch` | `references/ecommerce-images.md#自定创意分批` | TensorsLab 图像 API |
| 参考构图迁移 | `reference-layout` | `references/ecommerce-images.md#参考构图迁移` | TensorsLab 图像 API |
| 风格系列变体 | `style-series` | `references/ecommerce-images.md#风格系列变体` | TensorsLab 图像 API |
| 多画幅适配 | `format-adaptation` | `references/ecommerce-images.md#多画幅适配` | 生成式适配，逐图审核 |
| 批量 SKU 模板生产 | `batch-sku` | `references/ecommerce-images.md#批量-sku-模板生产` | 先样张，后批量 |
| 局部替换规划 | `local-replace` | `references/ecommerce-images.md#局部替换规划` | 需遮罩 API 或后期工具 |
| 商品展示、社媒广告或活动视频 | `product-showcase-video` / `social-ad-video` / `campaign-video` | `references/ecommerce-videos.md` | TensorsLab 视频 API |
| 审核、重试、交付 | — | `references/quality-gates.md` | 本地 QA 记录 |

If a job combines images and video, complete and approve the image plan first; pass an approved image into the video plan.

## Intake and asset rules

For every commercial run, collect only what the selected scenario needs:

- product name or SKU, channel, language, ratio and final output count;
- source assets and their responsibilities;
- immutable visible facts: shape, color, material, packaging, Logo, accessories and proportions;
- brand anchors: palette, lighting, composition, references and prohibited styles;
- the user's provided confirmation that they may use the assets and references.

Product fact images establish product identity. Visual references may supply only composition, palette, light, material treatment, typography rhythm and atmosphere. Never inherit a reference's brand, product parameters, copy, claims or logos. Never invent specifications, certifications, price, ranking, performance claims or platform-policy guarantees.

Keep critical copy, prices, claims and legal text in approved deterministic artwork or post-production rather than asking a generation model to render them.

## Create and approve a run

Create a local draft before any paid call. Example for a five-screen listing kit:

```bash
python skills/miaodashi-workshop/scripts/create_run.py \
  --project spring-jacket-launch \
  --scenario listing-kit \
  --platform douyin \
  --source ./jacket-front.jpg \
  --source ./jacket-back.jpg
```

The command creates `.miaodashi_output/<project>/`:

```text
plan.json       # tasks, facts, asset roles and execution boundary
prompts.md      # reviewable prompt worksheet
manifest.json   # task attempts, outputs and resumable state
qa.json         # review findings and retry notes
assets/         # reserved for organized local inputs
outputs/        # reserved for final delivery files
```

Fill `constraints.immutable_facts`, `constraints.brand_anchors` and every task prompt in `plan.json`; show the equivalent plan to the user. After they explicitly approve it, record that decision:

```bash
python skills/miaodashi-workshop/scripts/approve_run.py \
  --run .miaodashi_output/spring-jacket-launch \
  --approved-by "user-confirmed"
```

For `batch-sku`, validate the required `sku,product_file` columns before planning. A minimal starter mapping is available at `examples/sku-mapping.csv`.

`local-replace` is intentionally different: it records an approved edit region but remains `approved_pending_capability` until a masking endpoint or a post-production compositor is available. Do not claim it ran through the current API.

## Execute and record results

For each task marked `approved_for_execution`, prepare the command before any paid call:

```bash
python skills/miaodashi-workshop/scripts/prepare_dispatch.py \
  --run .miaodashi_output/spring-jacket-launch \
  --model seedreamv45 \
  --image-resolution 4:5
```

It writes `dispatch.json` with the exact `tl-image` or `tl-video` command for every planned, failed or QA-failed item. Review this file, then invoke the matching existing TensorsLab client under `skills/tl-image/` or `skills/tl-video/`. Do not construct a parallel HTTP client in this skill, and do not execute a command before the user approves the plan.

Once a task returns, record the exact output path or durable output URL and its review result:

```bash
python skills/miaodashi-workshop/scripts/record_result.py \
  --run .miaodashi_output/spring-jacket-launch \
  --task "主图" \
  --status completed \
  --output .miaodashi_output/spring-jacket-launch/outputs/hero.png \
  --task-id task_123 \
  --qa product_truth=pass \
  --qa visual_quality=pass
```

Use `failed` or `qa_failed` when appropriate. The manifest keeps successful tasks untouched and flags only the failed task for retry. Never write API keys, bearer tokens or raw authorization headers to plans, manifests, notes or errors.

## Miaodashi handoff

Offer [miaodashi.com](https://miaodashi.com) only when the user asks for a no-code workflow, managed delivery, collaborative review or large-scale production. Keep the API workflow self-contained for developers.
