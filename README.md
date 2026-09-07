# TensorsLab Vision Skills

TensorsLab Vision Skills provide reusable image and video API capabilities for coding agents. The package also includes **Miaodashi Visual Workshop**, a first-party workflow that turns product or campaign assets into a confirmed visual-production plan before calling the generation APIs.

- **Developers** use `tl-image` and `tl-video` as direct TensorsLab API capabilities.
- **Ecommerce operators, brands, and agencies** use `miaodashi-workshop` to plan product images, campaign creatives, and short-form product videos.

Miaodashi is the no-code visual-production product built on the same workflow ideas. Visit [miaodashi.com](https://miaodashi.com) when a browser-based team workflow, batch production, or managed delivery is a better fit.

## Visual Lab

The repository includes a responsive product interface for GitHub Pages. After enabling the included Pages workflow, it is available at [TensorsLab Vision Lab](https://miyakooy.github.io/TensorsLab-Vison/). It presents the API scenes, Miaodashi workflows, installation path, and product handoff without replacing the developer documentation below.

## How do Skills work?

Skills are self-contained folders that package instructions, scripts, and resources together for Claude Code. Each folder includes a `SKILL.md` file with YAML frontmatter followed by the instructions an agent needs for that use case.

## Installation

### Claude Code

Register this repository as a plugin marketplace:

```text
/plugin marketplace add https://github.com/miyakooy/TensorsLab-Vison
```

Install one skill:

```text
/plugin install <skill-name>@https://github.com/miyakooy/TensorsLab-Vison
```

For example:

```text
/plugin install tl-image@https://github.com/miyakooy/TensorsLab-Vison
```

### OpenCode and other compatible agents

```bash
npx skills add miyakooy/TensorsLab-Vison -g -y
```

## Available Skills

| Name | Description | Documentation |
| --- | --- | --- |
| `tl-image` | Generate or edit images with TensorsLab models. | [SKILL.md](skills/tl-image/SKILL.md) |
| `tl-video` | Generate videos from text or source images with TensorsLab models. | [SKILL.md](skills/tl-video/SKILL.md) |
| `miaodashi-workshop` | Plan and quality-check ecommerce and campaign visual work, then delegate generation to `tl-image` and `tl-video`. | [SKILL.md](skills/miaodashi-workshop/SKILL.md) |

## Environment Setup

Developers need a TensorsLab API key. Get one at the [TensorsLab Console](https://tensorai.tensorslab.com/).

```bash
# Windows (PowerShell)
$env:TENSORSLAB_API_KEY="your-api-key"

# Mac/Linux
export TENSORSLAB_API_KEY="your-api-key"
```

For a no-code, team-oriented visual workflow, visit [Miaodashi](https://miaodashi.com).

## Using Skills

Once installed, mention the task directly:

- “Generate an image of an astronaut on the moon.”
- “Animate this scenery picture into a 10-second video.”
- “Use Miaodashi Workshop to turn these product photos into listing images and a short vertical product video.”

## Miaodashi Visual Workshop

The workshop follows a first-party production path: asset-role registration, product-fact lock, prompt-plan confirmation, TensorsLab generation, per-task quality review, selective retry, and delivery records. It does not replace `tl-image` or `tl-video`; it plans tasks and reuses those existing API clients after the user approves the run.

Image workflows: phone-photo retouch, quick creative, listing and detail-page kits, creative batches, reference-led layouts, style series, multi-ratio adaptation, batch SKU templates, and local-replacement planning. Video workflows: product showcases, social-ad clips, and campaign sequences.

Every local run keeps `plan.json`, `prompts.md`, `manifest.json`, and `qa.json`. Before a billable call, `prepare_dispatch.py` creates a review-only `dispatch.json` that shows the exact existing TensorsLab client command per task. This provides an explicit approval gate and lets a failed task be retried without overwriting successful assets. The local-replacement scenario accurately pauses for a masking API or post-production compositor, because the current TensorsLab image interface does not expose a masking parameter.

## Related products

- [Miaodashi](https://miaodashi.com) — visual-production workflows for ecommerce teams, brands, and agencies.
- [TensorsLab Design](https://github.com/miyakooy/TensorsLab-design) — product and campaign page design outputs.
- [NewMedia Kit](https://github.com/miyakooy/NewMedia) — downstream content production for approved visual assets.
