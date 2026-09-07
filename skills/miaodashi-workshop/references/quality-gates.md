# Miaodashi quality gates

Review every generated item before calling it deliverable. Record a pass, retry, or human-review result in the run plan.

## Product truth

- Preserve product silhouette, color, material, package, visible label, logo, accessories, and proportions.
- Do not add unprovided claims, certifications, prices, rankings, or comparison statements.
- Reject images that change the product into a different SKU or introduce misleading accessories.

## Visual quality

- Check subject isolation, crop, hands, edges, reflections, shadows, and obvious deformation.
- Check that style, lighting, and camera direction match the approved plan.
- For video, check first frame, final frame, primary motion, product stability, and edit handoff.

## Text, rights, and publication

- Do not treat generated text as publication-ready. Add critical copy in a deterministic post-production step.
- Require the user to confirm rights for product images, brand material, people, and any supplied references.
- Treat ratio suggestions as creative defaults. The publisher remains responsible for validating current channel rules and advertising requirements.

## Retry policy

Retry only the failed task. Preserve the approved prompt and immutable facts; state the specific correction in the retry instruction. Do not silently change the creative direction or product facts.
