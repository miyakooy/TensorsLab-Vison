# TensorsLab Image Generation Scenarios

## Important: Single Script, Different Prompts

All scenarios below use the same script `scripts/tensorslab_image.py`. The difference is in the **prompt engineering** - each scenario requires specific prompt templates and enhancements to achieve the desired effect.

These are **best-effort generative transformations**, not separate product capabilities. The repository does not provide masks, region coordinates, identity verification, OCR cleanup, or deterministic inpainting. Do not promise exact watermark removal, exact object boundaries, or identity-preserving face replacement. Confirm that the user has the rights and consent needed for the supplied assets.

## Avatar Generation

Generate profile/avatar images in various styles. Supports both generation from text description and generation based on a reference image.

**User Input Examples:**
- "帮我生成一个二次元风格的头像"
- "生成一个专业的商务头像"
- "参考 `./photo.jpg` 生成一个卡通风格的头像"
- "用 `./selfie.png` 做一个二次元头像"

**Agent Processing:**
1. Identify avatar generation intent from keywords (头像, avatar, profile)
2. Check if reference image is provided
3. Extract style description (二次元/写实/商务/卡通)
4. Add square size parameter: `--resolution 1:1`
5. Build enhanced prompt with avatar-specific details

**Prompt Template (Without Reference):**
```
A professional [style] avatar portrait, [style-specific details],
clean background suitable for profile picture,
high quality, centered composition, [additional style enhancements]

Style examples:
- 二次元: anime style portrait, vibrant colors, large expressive eyes,
  cel-shaded style, clean solid background
- 写实: photorealistic portrait, natural lighting, professional headshot,
  soft focus background, studio lighting
- 商务: professional business avatar, clean and modern,
  neutral background, confident expression, corporate style
- 卡通: cute cartoon avatar, fun and playful style,
  illustrated look, cheerful expression, colorful background
```

**Prompt Template (With Reference):**
```
Generate an avatar based on the reference image. Transform the person
into [style] style while preserving facial features and identity.
Clean background suitable for profile picture, high quality,
centered composition.

Style transformation examples:
- 二次元: Transform into anime/manga style with cel-shaded rendering,
  vibrant colors, large expressive eyes, clean solid background
- 写实: Enhance as professional photorealistic headshot with
  studio lighting, soft focus background
- 商务: Transform into professional business avatar with
  neutral background, confident expression, corporate style
- 卡通: Transform into cute cartoon style with fun illustrated look,
  cheerful expression, colorful background
```

**Commands:**
```bash
# Without reference image
python scripts/tensorslab_image.py "[enhanced prompt]" --resolution 1:1

# With reference image
python scripts/tensorslab_image.py "[enhanced prompt]" --source ./photo.jpg --resolution 1:1
```

---

## Watermark Removal

Attempt to remove a watermark through generative reconstruction. Results may change nearby texture or content; use a licensed source or deterministic editor when exact preservation matters.

**User Input Examples:**
- "帮我去掉 `./image.jpg` 的水印"
- "去除这张图片的水印"
- "去掉 `./photo.png` 上的logo"

**Agent Processing:**
1. Extract image file path
2. Build precise watermark removal prompt
3. Call script with source image and removal prompt

**Prompt Template:**
```
Remove watermark from image while preserving background texture
and visual integrity. Intelligently fill the watermark area with
surrounding content patterns, maintaining seamless visual continuity.
No text or logos should remain. Original image quality and composition
should be preserved.
```

**Command:**
```bash
python scripts/tensorslab_image.py "[removal prompt]" --source ./image.jpg
```

---

## Object Erasure

Attempt to remove unwanted objects or people through generative reconstruction. The client does not accept a mask, so the changed area cannot be guaranteed.

**User Input Examples:**
- "把 `./photo.jpg` 里多余的路人擦掉"
- "去掉背景里的这块杂物"
- "移除图片中的人物"

**Agent Processing:**
1. Extract image file path
2. Identify the object to be removed
3. Build precise erasure prompt specifying the object
4. Call script with source image and erasure prompt

**Prompt Template:**
```
Remove the [object description] from the image. Intelligently fill
the area with appropriate background content that maintains natural
scene consistency. The fill should match surrounding textures,
lighting, and perspective. No visual artifacts or irregularities
should remain at the removal site.

Object examples:
- 多余的路人: Remove the extra people/passersby from the background
- 杂物: Remove the clutter/debris from the scene
- 人物: Remove the person/figure from the image
```

**Command:**
```bash
python scripts/tensorslab_image.py "[erasure prompt]" --source ./photo.jpg
```

---

## Face Replacement

Attempt a consented face transformation using two references. The endpoint is general image-to-image generation, not a dedicated face-swap service, so identity and placement are not guaranteed.

**User Input Examples:**
- "把 `./face.jpg` 的人脸换到 `./target.jpg` 上"
- "用 `./portrait.png` 的脸替换 `./group.jpg` 里的第一个人"

**Agent Processing:**
1. Extract TWO image file paths:
   - Source face image (the face to use)
   - Target image (where to place the face)
2. Build precise face replacement prompt
3. Call script with both source images (face first, then target)
4. Specify which face to replace in the prompt if target has multiple people

**Prompt Template:**
```
Replace the [face description] in the second image with the face
from the first image. Match skin tone, lighting angle, and expression
naturally. Ensure seamless blending at the edges of the face replacement.
Preserve the original head orientation and perspective in the target image.
The result should look natural and undetectable as an edit.

Additional considerations:
- 皮肤匹配: Match skin texture and tone to target image lighting
- 光照角度: Align facial lighting with scene light source
- 表情自然: Maintain natural facial expression appropriate to scene
- 边缘融合: Seamless edge blending between face and surrounding area

Face description examples (for target image with multiple faces):
- 第一个人/最左边的人: the first person from the left
- 中间的人: the person in the center
- 右边的人: the person on the right
```

**Command:**
```bash
python scripts/tensorslab_image.py "[replacement prompt]" --source ./face.jpg --source ./target.jpg
```

**Note:** Both images are passed via `--source` parameters. The first source is the face to use, the second source is the target image where the replacement happens.
