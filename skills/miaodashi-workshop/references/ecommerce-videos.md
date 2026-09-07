# 电商视频工作流

## 共享视频规则

Use approved images as source frames whenever product identity matters. Give every clip one main action and one camera intention. Generate clips independently, then prepare them for editing; do not expect a single generation to complete a multi-scene ad reliably.

## 商品展示短片

**Use for:** a short product reveal or a catalog-quality motion asset.

**Collect:** one approved hero image, product facts, target ratio, duration, intended action, and target channel.

**Plan:** create one 5–10 second clip. Describe subject motion, camera movement, lighting continuity, and a clean exit frame. Use `tl-video` image-to-video mode.

**Prompt structure:**

```text
Animate the supplied product image. Preserve the product's shape, color,
label, material, and proportions. [Subject motion]. [Camera movement].
[Lighting and background continuity]. No new text, logos, extra products,
or product deformation. End on a clean [wide / medium / close] frame.
```

## 社媒广告镜头组

**Use for:** vertical or horizontal paid-social creative variants.

**Collect:** approved key visual, one approved product benefit, target ratio, duration, hook direction, and optional CTA text for post-production.

**Plan:** make a short visual hook, product-focused action, and a clean ending with copy-safe space. Output one visual-only variant per task; add final copy in post-production.

## 活动视频序列

**Use for:** a short edit made from multiple approved stills or clips.

**Collect:** three to five approved image assets, visual order, duration budget, transition preference, and audio requirements.

**Plan:** assign one source asset and one action to each clip. Make the final frame of a clip compatible with the opening frame of the next. If `seedancev2` is selected, use only its supported optional audio and final-frame flags; otherwise omit them.

## 未被 API 支持时不得承诺

Do not advertise lip-synced dialogue, multi-character performance, frame-perfect camera continuity, or start-and-end-frame control unless the chosen TensorsLab video endpoint exposes those inputs and the user has approved the result plan.
