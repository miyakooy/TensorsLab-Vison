# TensorsLab Vision 作品与场景 / Showcase

<p>
  <a href="README.md">简体中文</a> · <a href="README.en.md">English</a> · <a href="README.ja.md">日本語</a> · <a href="README.ko.md">한국어</a>
</p>

这里展示可以继续沉淀为社区场景包的视觉案例。图片来自 [miaodashi.com](https://miaodashi.com) 已公开的视觉展示；它们用于说明目标交付物，不代表每个步骤都已经由本仓库自动完成。

社区场景包的目标不是只展示成片，而是补齐：原始素材、约束、可复用 Prompt、模型参数、运行记录、质量门禁和已知限制。

## 电商商品短视频 / Ecommerce product video

<p align="center">
  <img src="https://miaodashi.com/cap-short-video.jpg" alt="电商厨具商品短视频与移动端竖屏内容示例" width="100%" />
</p>

- **当前支持：** 使用已确认的商品主图创建 `product-showcase-video` 或 `social-ad-video` 计划，再复用 `tl-video` 逐镜生成。
- **仍需人工：** 可控口播台词、精确口型、字幕和最终剪辑。
- **适合贡献：** 口播带货、卖点展示、开箱和社媒广告镜头模板。

## 商品清理与对比 / Product cleanup and comparison

<p align="center">
  <img src="https://miaodashi.com/cap-comparison-video.jpg" alt="商品场景清理前后对比视觉示例" width="100%" />
</p>

- **当前支持：** 通用图生图提示词、前后对比任务规划、结果和 QA 记录。
- **能力边界：** 当前仓库没有遮罩 API；精确局部消除属于生成式尽力而为。
- **适合贡献：** 可复现的输入图、允许修改的区域、失败案例和人工验收规则。

## 商品详情页视觉组 / Product detail-page kit

<p align="center">
  <img src="https://miaodashi.com/cap-poster.jpg" alt="电商商品卖点、功能、尺寸与详情页视觉组示例" width="100%" />
</p>

- **当前支持：** `listing-kit` 将主图、结构、材质、场景和包装拆成独立任务。
- **仍需人工：** 价格、参数、合规声明和其他关键文字应使用确定性排版工具添加。
- **适合贡献：** Amazon、TikTok Shop、淘宝、小红书等平台的输出规格和质量清单。

## 泛娱乐人物特效 / Entertainment portrait effects

<p align="center">
  <img src="https://miaodashi.com/scene-beauty-effects.webp" alt="多人像统一视觉特效的泛娱乐模板参考" width="100%" />
</p>

- **当前支持：** 多参考图输入和通用图生图的风格化尝试。
- **能力边界：** 这不是专用的 `faceswap`、`face-swap` 或 Deepfake 接口，人物身份一致性需要逐张审核。
- **安全要求：** 只接受拥有使用权且相关人物已经同意的素材，不接受冒充、欺诈或未经同意的人脸替换案例。

## 把作品变成可复现用例

提交作品时，请同时提供：

1. 目标场景、平台、语言、比例和交付数量；
2. 可公开或已脱敏的输入素材；
3. 使用的 Skill、模型、Prompt 和参数；
4. 成功输出与至少一个失败或 QA 不通过的样本；
5. 商品事实、人物授权和素材使用权说明；
6. 当前不能自动完成、仍需后期处理的步骤。

请使用 [作品与场景贡献表单](../.github/ISSUE_TEMPLATE/showcase.yml) 发起贡献。执行逻辑继续复用 `tl-image`、`tl-video` 和 `miaodashi-workshop`，场景包不重新实现 API 客户端。
