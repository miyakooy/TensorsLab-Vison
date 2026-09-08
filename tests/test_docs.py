from __future__ import annotations

import json
import re
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
READMES = [
    ROOT / "README.md",
    ROOT / "README.zh-CN.md",
    ROOT / "README.ja.md",
    ROOT / "README.ko.md",
    ROOT / "CONTRIBUTING.md",
    ROOT / "examples/README.md",
    ROOT / "examples/README.en.md",
    ROOT / "examples/README.ja.md",
    ROOT / "examples/README.ko.md",
    ROOT / "docs/README.md",
]

PAGE_URLS = {
    ROOT / "docs/index.html": "https://miyakooy.github.io/TensorsLab-Vison/",
    ROOT / "docs/en/index.html": "https://miyakooy.github.io/TensorsLab-Vison/en/",
    ROOT / "docs/ja/index.html": "https://miyakooy.github.io/TensorsLab-Vison/ja/",
    ROOT / "docs/ko/index.html": "https://miyakooy.github.io/TensorsLab-Vison/ko/",
}

HREFLANGS = {
    "zh-Hans": "https://miyakooy.github.io/TensorsLab-Vison/",
    "en": "https://miyakooy.github.io/TensorsLab-Vison/en/",
    "ja": "https://miyakooy.github.io/TensorsLab-Vison/ja/",
    "ko": "https://miyakooy.github.io/TensorsLab-Vison/ko/",
    "x-default": "https://miyakooy.github.io/TensorsLab-Vison/",
}


class DocumentationTests(unittest.TestCase):
    def test_each_locale_uses_localized_illustrations(self) -> None:
        localized_assets = {
            "README.md": [
                "api-scenes.svg",
                "workshop-flow.svg",
                "quality-gates.svg",
            ],
            "README.zh-CN.md": [
                "api-scenes.zh-CN.svg",
                "workshop-flow.zh-CN.svg",
                "quality-gates.zh-CN.svg",
            ],
            "README.ja.md": [
                "api-scenes.ja.svg",
                "workshop-flow.ja.svg",
                "quality-gates.ja.svg",
            ],
            "README.ko.md": [
                "api-scenes.ko.svg",
                "workshop-flow.ko.svg",
                "quality-gates.ko.svg",
            ],
        }
        for readme_name, asset_names in localized_assets.items():
            content = (ROOT / readme_name).read_text(encoding="utf-8")
            for asset_name in asset_names:
                self.assertIn(f'docs/assets/{asset_name}', content, readme_name)

    def test_local_readme_links_exist(self) -> None:
        markdown_link = re.compile(r"!?\[[^]]*\]\(([^)]+)\)")
        html_target = re.compile(r"(?:href|src)=\"([^\"]+)\"")
        missing: list[str] = []
        for readme in READMES:
            content = readme.read_text(encoding="utf-8")
            targets = markdown_link.findall(content) + html_target.findall(content)
            for target in targets:
                if target.startswith(("http://", "https://", "#", "mailto:")):
                    continue
                path_text = target.split("#", 1)[0]
                if path_text and not (readme.parent / path_text).resolve().exists():
                    missing.append(f"{readme.relative_to(ROOT)} -> {target}")
        self.assertEqual(missing, [])

    def test_sitemap_is_valid_xml(self) -> None:
        root = ET.parse(ROOT / "docs/sitemap.xml").getroot()
        locations = [item.text for item in root.findall("{*}url/{*}loc")]
        self.assertEqual(set(locations), set(PAGE_URLS.values()))

    def test_showcase_assets_are_local_and_indexable(self) -> None:
        assets = [
            "ai-poster-design.png",
            "ai-scene-composition.png",
            "ai-ecommerce-main-image.png",
            "ai-ecommerce-product-set.png",
        ]
        sitemap = (ROOT / "docs/sitemap.xml").read_text(encoding="utf-8")
        for asset in assets:
            self.assertTrue((ROOT / "docs/assets/showcase" / asset).is_file(), asset)
            self.assertIn(f"assets/showcase/{asset}", sitemap)
        for page in PAGE_URLS:
            html = page.read_text(encoding="utf-8")
            self.assertIn("assets/showcase/ai-ecommerce-main-image.png", html)

    def test_localized_pages_have_reciprocal_hreflang(self) -> None:
        for page, canonical_url in PAGE_URLS.items():
            html = page.read_text(encoding="utf-8")
            self.assertIn(f'<link rel="canonical" href="{canonical_url}"', html)
            for language, url in HREFLANGS.items():
                self.assertIn(
                    f'<link rel="alternate" hreflang="{language}" href="{url}"',
                    html,
                    page.name,
                )

    def test_json_ld_is_valid(self) -> None:
        html = (ROOT / "docs/index.html").read_text(encoding="utf-8")
        match = re.search(
            r'<script type="application/ld\+json">\s*(.*?)\s*</script>',
            html,
            flags=re.DOTALL,
        )
        self.assertIsNotNone(match)
        payload = json.loads(match.group(1))
        self.assertEqual(payload["@type"], "SoftwareSourceCode")
        self.assertEqual(payload["codeRepository"], "https://github.com/miyakooy/TensorsLab-Vison")
        self.assertIn("image to video", payload["keywords"])

    def test_showcase_keeps_capability_boundaries_visible(self) -> None:
        html = (ROOT / "docs/index.html").read_text(encoding="utf-8")
        self.assertIn('id="showcase"', html)
        self.assertIn("WORKFLOW READY", html)
        self.assertIn("BEST EFFORT", html)
        self.assertIn("不是专用 faceswap", html)

    def test_marketplace_sources_are_installable_skill_folders(self) -> None:
        marketplace = json.loads(
            (ROOT / ".claude-plugin/marketplace.json").read_text(encoding="utf-8")
        )
        self.assertEqual(marketplace["name"], "tensorslab-skills")
        for plugin in marketplace["plugins"]:
            source = (ROOT / plugin["source"]).resolve()
            self.assertTrue(source.is_dir(), plugin["name"])
            skill_file = source / "SKILL.md"
            self.assertTrue(skill_file.is_file(), plugin["name"])
            frontmatter = skill_file.read_text(encoding="utf-8").split("---", 2)[1]
            self.assertIn("name:", frontmatter)
            self.assertIn("description:", frontmatter)


if __name__ == "__main__":
    unittest.main()
