#!/usr/bin/env python3
"""Create a reviewable Miaodashi visual-production run without API calls.

This script deliberately creates only local records. TensorsLab's existing
``tl-image`` and ``tl-video`` clients remain the sole route for generation
after a user has approved the plan.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


RATIO_PATTERN = re.compile(r"^[1-9][0-9]*:[1-9][0-9]*$")

SCENARIOS: dict[str, dict[str, Any]] = {
    "phone-retouch": {
        "kind": "image",
        "label": "手机商品精修",
        "reference": "references/ecommerce-images.md#手机商品精修",
        "source_min": 1,
        "source_max": 5,
        "default_output_count": 1,
        "max_output_count": 5,
        "execution_level": "direct_api",
        "tasks": [],
    },
    "quick-creative": {
        "kind": "image",
        "label": "快捷创意图",
        "reference": "references/ecommerce-images.md#快捷创意图",
        "source_min": 0,
        "source_max": 5,
        "default_output_count": 1,
        "max_output_count": 10,
        "execution_level": "direct_api",
        "tasks": [],
    },
    "listing-kit": {
        "kind": "image",
        "label": "主图与详情页视觉组",
        "reference": "references/ecommerce-images.md#主图与详情页视觉组",
        "source_min": 1,
        "source_max": 8,
        "default_output_count": 5,
        "max_output_count": 12,
        "execution_level": "direct_api",
        "tasks": ["主图", "结构展示", "材质细节", "使用场景", "包装与配件"],
    },
    "creative-batch": {
        "kind": "image",
        "label": "自定创意分批",
        "reference": "references/ecommerce-images.md#自定创意分批",
        "source_min": 0,
        "source_max": 8,
        "default_output_count": 3,
        "max_output_count": 20,
        "execution_level": "direct_api",
        "tasks": [],
    },
    "reference-layout": {
        "kind": "image",
        "label": "参考构图迁移",
        "reference": "references/ecommerce-images.md#参考构图迁移",
        "source_min": 1,
        "source_max": 4,
        "reference_min": 1,
        "reference_max": 1,
        "default_output_count": 1,
        "max_output_count": 4,
        "execution_level": "direct_api",
        "tasks": [],
    },
    "style-series": {
        "kind": "image",
        "label": "风格系列变体",
        "reference": "references/ecommerce-images.md#风格系列变体",
        "source_min": 0,
        "source_max": 5,
        "reference_min": 1,
        "reference_max": 5,
        "default_output_count": 3,
        "max_output_count": 10,
        "execution_level": "direct_api",
        "tasks": [],
    },
    "format-adaptation": {
        "kind": "image",
        "label": "多画幅适配",
        "reference": "references/ecommerce-images.md#多画幅适配",
        "source_min": 1,
        "source_max": 20,
        "default_output_count": 1,
        "max_output_count": 60,
        "execution_level": "direct_api_with_review",
        "tasks": [],
    },
    "batch-sku": {
        "kind": "image",
        "label": "批量 SKU 模板生产",
        "reference": "references/ecommerce-images.md#批量-sku-模板生产",
        "source_min": 0,
        "source_max": 0,
        "default_output_count": 1,
        "max_output_count": 20,
        "execution_level": "direct_api_after_sample",
        "tasks": [],
    },
    "local-replace": {
        "kind": "image",
        "label": "局部替换规划",
        "reference": "references/ecommerce-images.md#局部替换规划",
        "source_min": 1,
        "source_max": 1,
        "product_min": 1,
        "product_max": 4,
        "default_output_count": 1,
        "max_output_count": 1,
        "execution_level": "plan_requires_mask_api",
        "tasks": ["确认选区后的局部替换"],
    },
    "product-showcase-video": {
        "kind": "video",
        "label": "商品展示短片",
        "reference": "references/ecommerce-videos.md#商品展示短片",
        "source_min": 1,
        "source_max": 2,
        "default_output_count": 1,
        "max_output_count": 1,
        "execution_level": "direct_api",
        "tasks": ["商品展示镜头"],
    },
    "social-ad-video": {
        "kind": "video",
        "label": "社媒广告镜头组",
        "reference": "references/ecommerce-videos.md#社媒广告镜头组",
        "source_min": 1,
        "source_max": 2,
        "default_output_count": 2,
        "max_output_count": 3,
        "execution_level": "direct_api",
        "tasks": ["视觉钩子镜头", "干净收束镜头"],
    },
    "campaign-video": {
        "kind": "video",
        "label": "活动视频序列",
        "reference": "references/ecommerce-videos.md#活动视频序列",
        "source_min": 1,
        "source_max": 2,
        "default_output_count": 3,
        "max_output_count": 5,
        "execution_level": "direct_api",
        "tasks": ["开场镜头", "产品动作镜头", "收束镜头"],
    },
}

# Kept so plans created with the first release can be migrated without forcing
# users to rewrite their command history.
ALIASES = {
    "apparel-listing": "listing-kit",
    "product-hero": "quick-creative",
    "detail-page": "listing-kit",
    "campaign-kv": "creative-batch",
    "sku-batch": "batch-sku",
}


def project_slug(value: str) -> str:
    slug = "".join(char.lower() if char.isalnum() else "-" for char in value).strip("-")
    if not slug:
        raise argparse.ArgumentTypeError("project must contain letters or numbers")
    return slug


def output_count(value: str) -> int:
    count = int(value)
    if count < 1:
        raise argparse.ArgumentTypeError("output count must be at least 1")
    return count


def normalized_region(value: str) -> list[float]:
    try:
        region = [float(item.strip()) for item in value.split(",")]
    except ValueError as error:
        raise argparse.ArgumentTypeError("region must be x,y,width,height using values from 0 to 1") from error
    if len(region) != 4 or any(item < 0 or item > 1 for item in region):
        raise argparse.ArgumentTypeError("region must be x,y,width,height using values from 0 to 1")
    x, y, width, height = region
    if width == 0 or height == 0 or x + width > 1 or y + height > 1:
        raise argparse.ArgumentTypeError("region must remain inside the source image")
    return region


def ratio(value: str) -> str:
    if not RATIO_PATTERN.fullmatch(value):
        raise argparse.ArgumentTypeError("ratio must look like 1:1, 4:5, or 9:16")
    return value


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create a Miaodashi production plan without generating assets."
    )
    parser.add_argument("--project", required=True, type=project_slug)
    parser.add_argument("--scenario", required=True, choices=sorted(set(SCENARIOS) | set(ALIASES)))
    parser.add_argument("--platform", default="generic")
    parser.add_argument("--source", action="append", default=[], help="Primary product or scene asset")
    parser.add_argument("--product", action="append", default=[], help="Replacement product asset")
    parser.add_argument("--reference", action="append", default=[], help="Style, layout, or template reference")
    parser.add_argument("--source-url", action="append", default=[], help="Remote primary asset URL")
    parser.add_argument("--ratio", action="append", default=[], type=ratio, help="Target output ratio; repeatable")
    parser.add_argument("--output-count", type=output_count, help="Number of planned creative outputs")
    parser.add_argument("--retouch-level", choices=["natural", "commerce", "studio"])
    parser.add_argument("--region", type=normalized_region, help="Normalized local edit area x,y,width,height")
    parser.add_argument("--sku-csv", help="CSV containing sku and product_file columns")
    parser.add_argument("--sku-assets-dir", help="Directory used to resolve product_file values")
    parser.add_argument("--template", help="The one approved layout template for batch-sku")
    parser.add_argument("--output-dir", default=".miaodashi_output")
    parser.add_argument(
        "--allow-missing-sources",
        action="store_true",
        help="Create the plan before local assets have arrived; their existence is still marked pending.",
    )
    return parser.parse_args()


def asset_record(value: str, role: str, allow_missing: bool) -> dict[str, str]:
    path = Path(value).expanduser()
    if not allow_missing and not path.is_file():
        raise FileNotFoundError(f"source file does not exist: {value}")
    return {
        "type": "local",
        "value": str(path),
        "role": role,
        "availability": "available" if path.is_file() else "pending",
    }


def url_record(value: str, role: str) -> dict[str, str]:
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError(f"source URL must use http or https: {value}")
    return {"type": "url", "value": value, "role": role, "availability": "not_downloaded"}


def check_count(label: str, items: list[object], minimum: int, maximum: int) -> None:
    if len(items) < minimum or len(items) > maximum:
        raise ValueError(f"this scenario needs {minimum}-{maximum} {label}; received {len(items)}")


def read_sku_rows(args: argparse.Namespace) -> list[dict[str, str]]:
    if not args.sku_csv or not args.template:
        raise ValueError("batch-sku requires both --sku-csv and --template")
    csv_path = Path(args.sku_csv).expanduser()
    template_path = Path(args.template).expanduser()
    if not args.allow_missing_sources and not csv_path.is_file():
        raise FileNotFoundError(f"source file does not exist: {args.sku_csv}")
    if not args.allow_missing_sources and not template_path.is_file():
        raise FileNotFoundError(f"source file does not exist: {args.template}")
    if not csv_path.is_file():
        return []
    with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        fields = set(reader.fieldnames or [])
        required = {"sku", "product_file"}
        if not required.issubset(fields):
            raise ValueError("SKU CSV must contain sku and product_file columns")
        rows = [{key: (value or "").strip() for key, value in row.items()} for row in reader]
    if not rows:
        raise ValueError("SKU CSV must include at least one row")
    if len(rows) > SCENARIOS["batch-sku"]["max_output_count"]:
        raise ValueError("batch-sku supports at most 20 rows per run")
    seen: set[str] = set()
    asset_dir = Path(args.sku_assets_dir).expanduser() if args.sku_assets_dir else csv_path.parent
    for row in rows:
        if not row["sku"] or not row["product_file"]:
            raise ValueError("every SKU row needs both sku and product_file")
        if row["sku"] in seen:
            raise ValueError(f"SKU appears more than once: {row['sku']}")
        seen.add(row["sku"])
        product_path = asset_dir / row["product_file"]
        if not args.allow_missing_sources and not product_path.is_file():
            raise FileNotFoundError(f"SKU product file does not exist: {product_path}")
        row["resolved_product_file"] = str(product_path)
    return rows


def build_asset_inventory(args: argparse.Namespace) -> tuple[list[dict[str, str]], list[dict[str, str]], list[dict[str, str]]]:
    sources = [asset_record(value, "primary source", args.allow_missing_sources) for value in args.source]
    sources.extend(url_record(value, "primary source") for value in args.source_url)
    products = [asset_record(value, "replacement product", args.allow_missing_sources) for value in args.product]
    references = [asset_record(value, "visual reference", args.allow_missing_sources) for value in args.reference]
    return sources, products, references


def creative_tasks(scenario: dict[str, Any], count: int) -> list[str]:
    base = list(scenario["tasks"])
    if base:
        if count <= len(base):
            return base[:count]
        return base + [f"扩展画面 {index:02d}" for index in range(len(base) + 1, count + 1)]
    return [f"创意画面 {index:02d}" for index in range(1, count + 1)]


def scenario_tasks(
    scenario_key: str,
    scenario: dict[str, Any],
    sources: list[dict[str, str]],
    sku_rows: list[dict[str, str]],
    ratios: list[str],
    count: int,
) -> list[dict[str, Any]]:
    if scenario_key == "phone-retouch":
        return [
            {
                "name": f"精修 {Path(source['value']).name or f'图 {index:02d}'}",
                "status": "planned",
                "prompt": "",
                "source_roles": [source["role"]],
                "input_assets": [source],
                "outputs": [],
            }
            for index, source in enumerate(sources, start=1)
        ]
    if scenario_key == "format-adaptation":
        return [
            {
                "name": f"{Path(source['value']).name or f'图 {source_index:02d}'} · {target_ratio}",
                "status": "planned",
                "prompt": "",
                "source_roles": [source["role"]],
                "input_assets": [source],
                "target_ratio": target_ratio,
                "outputs": [],
            }
            for source_index, source in enumerate(sources, start=1)
            for target_ratio in ratios
        ]
    if scenario_key == "batch-sku":
        return [
            {
                "name": f"SKU {row['sku']}",
                "status": "planned",
                "prompt": "",
                "source_roles": ["SKU product", "approved template"],
                "sku": row["sku"],
                "product_file": row["resolved_product_file"],
                "mapped_fields": {key: value for key, value in row.items() if key not in {"sku", "product_file", "resolved_product_file"} and value},
                "outputs": [],
            }
            for row in sku_rows
        ]
    return [
        {"name": name, "status": "planned", "prompt": "", "source_roles": [], "outputs": []}
        for name in creative_tasks(scenario, count)
    ]


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def prompt_template(scenario: dict[str, Any], tasks: list[dict[str, Any]]) -> str:
    instructions = ""
    if scenario["execution_level"] == "plan_requires_mask_api":
        instructions = (
            "\n> 当前安装的 TensorsLab 图像接口没有遮罩局部编辑参数。先确认选区和替换规则；"
            "在具备遮罩接口或后期合成工具后再执行。\n"
        )
    return (
        f"# {scenario['label']}\n\n"
        "此文件是草案，不触发 API 调用。补齐内容后，先向用户展示完整计划并获得批准。\n"
        f"{instructions}\n"
        "## 不可改变的商品事实\n"
        "- 产品 / SKU：[名称]\n"
        "- 必须保留：[形状、颜色、材质、包装、标签、配件、比例]\n"
        "- 禁止：[未批准改动、无依据卖点、生成文字、参考图品牌或 Logo]\n\n"
        "## 已批准的任务提示词\n"
        + "\n".join(f"- [ ] {task['name']}：[提示词]" for task in tasks)
        + f"\n\n## 执行方式\n批准后复用现有 `tl-{scenario['kind']}` TensorsLab 客户端逐项执行；"
        "每项完成后使用 `record_result.py` 登记输出和质检结果。\n"
    )


def main() -> int:
    args = parse_args()
    scenario_key = ALIASES.get(args.scenario, args.scenario)
    scenario = SCENARIOS[scenario_key]
    requested_count = args.output_count or scenario["default_output_count"]
    if requested_count > scenario["max_output_count"]:
        print(f"Error: {scenario_key} allows at most {scenario['max_output_count']} planned outputs", file=sys.stderr)
        return 2
    try:
        sources, products, references = build_asset_inventory(args)
        check_count("primary source assets", sources, scenario["source_min"], scenario["source_max"])
        check_count("visual references", references, scenario.get("reference_min", 0), scenario.get("reference_max", 99))
        check_count("replacement product assets", products, scenario.get("product_min", 0), scenario.get("product_max", 99))
        if scenario_key in {"phone-retouch", "format-adaptation", "batch-sku", "local-replace"} and args.output_count:
            raise ValueError(f"--output-count is derived from the supplied assets for {scenario_key}")
        if scenario_key == "format-adaptation" and not args.ratio:
            raise ValueError("format-adaptation needs at least one --ratio")
        if scenario_key != "format-adaptation" and args.ratio:
            raise ValueError("--ratio is only used by format-adaptation; record other ratios in prompts.md")
        if scenario_key == "local-replace" and not args.region:
            raise ValueError("local-replace needs a normalized --region for user confirmation")
        if scenario_key != "local-replace" and args.region:
            raise ValueError("--region is only used by local-replace")
        if scenario_key == "phone-retouch" and not args.retouch_level:
            raise ValueError("phone-retouch needs --retouch-level natural, commerce, or studio")
        if scenario_key != "phone-retouch" and args.retouch_level:
            raise ValueError("--retouch-level is only used by phone-retouch")
        sku_rows = read_sku_rows(args) if scenario_key == "batch-sku" else []
        if scenario_key != "batch-sku" and any([args.sku_csv, args.sku_assets_dir, args.template]):
            raise ValueError("SKU options are only used by batch-sku")
    except (FileNotFoundError, ValueError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 2

    tasks = scenario_tasks(scenario_key, scenario, sources, sku_rows, args.ratio, requested_count)
    if len(tasks) > scenario["max_output_count"]:
        print(f"Error: this input creates {len(tasks)} tasks; the scenario limit is {scenario['max_output_count']}", file=sys.stderr)
        return 2

    run_dir = Path(args.output_dir).expanduser() / args.project
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "assets").mkdir(exist_ok=True)
    (run_dir / "outputs").mkdir(exist_ok=True)

    created_at = datetime.now(timezone.utc).isoformat()
    batch_sku = None
    if scenario_key == "batch-sku":
        batch_sku = {
            "csv": str(Path(args.sku_csv).expanduser()),
            "asset_directory": str(Path(args.sku_assets_dir).expanduser()) if args.sku_assets_dir else str(Path(args.sku_csv).expanduser().parent),
            "template": asset_record(args.template, "approved template", args.allow_missing_sources),
        }

    plan = {
        "schema_version": 2,
        "project": args.project,
        "scenario": scenario_key,
        "requested_scenario": args.scenario,
        "scenario_label": scenario["label"],
        "kind": scenario["kind"],
        "platform": args.platform,
        "created_at": created_at,
        "status": "draft_needs_approval",
        "asset_roles": {"primary_sources": sources, "replacement_products": products, "visual_references": references},
        "constraints": {
            "immutable_facts": [],
            "brand_anchors": [],
            "prohibited_changes": [],
            "target_ratios": args.ratio,
            "retouch_level": args.retouch_level,
            "local_edit_region": args.region,
        },
        "tasks": tasks,
        "execution": {
            "skill": f"tl-{scenario['kind']}",
            "reference": scenario["reference"],
            "level": scenario["execution_level"],
            "approved_by_user": False,
            "approved_at": None,
        },
    }
    if batch_sku:
        plan["batch_sku"] = batch_sku
    manifest = {
        "schema_version": 1,
        "project": args.project,
        "status": "draft",
        "created_at": created_at,
        "task_status": {task["name"]: {"status": "planned", "outputs": [], "attempts": []} for task in tasks},
        "resume_policy": "retry only failed or qa_failed tasks; never overwrite approved outputs without explicit permission",
    }
    qa = {
        "schema_version": 1,
        "project": args.project,
        "status": "not_started",
        "checks": {"product_truth": "pending", "visual_quality": "pending", "text_and_rights": "pending", "publication_review": "pending"},
        "retry_notes": [],
    }

    write_json(run_dir / "plan.json", plan)
    write_json(run_dir / "manifest.json", manifest)
    write_json(run_dir / "qa.json", qa)
    (run_dir / "prompts.md").write_text(prompt_template(scenario, tasks), encoding="utf-8")

    print(f"Created Miaodashi run plan: {run_dir}")
    print("Next: fill factual constraints and prompts, obtain explicit approval with approve_run.py, then reuse the existing tl-image or tl-video client task by task.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
