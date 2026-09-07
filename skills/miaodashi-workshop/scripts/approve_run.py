#!/usr/bin/env python3
"""Move a completed local Miaodashi plan to explicit user approval."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise ValueError(f"missing run file: {path.name}") from error
    if not isinstance(value, dict):
        raise ValueError(f"invalid JSON object: {path.name}")
    return value


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Record explicit approval for a filled Miaodashi plan.")
    parser.add_argument("--run", required=True, help="Path to a run folder containing plan.json")
    parser.add_argument("--approved-by", required=True, help="Person or approval reference supplied by the user")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    run_dir = Path(args.run).expanduser()
    try:
        plan = read_json(run_dir / "plan.json")
        manifest = read_json(run_dir / "manifest.json")
    except ValueError as error:
        print(f"Error: {error}", file=sys.stderr)
        return 2

    if plan.get("status") != "draft_needs_approval":
        print("Error: only a draft_needs_approval plan can be approved", file=sys.stderr)
        return 2
    constraints = plan.get("constraints", {})
    missing = []
    if not constraints.get("immutable_facts"):
        missing.append("constraints.immutable_facts")
    if not constraints.get("brand_anchors"):
        missing.append("constraints.brand_anchors")
    if not plan.get("tasks") or any(not task.get("prompt", "").strip() for task in plan["tasks"]):
        missing.append("a non-empty prompt for every task")
    if missing:
        print("Error: complete " + ", ".join(missing) + " before approval", file=sys.stderr)
        return 2

    approved_at = datetime.now(timezone.utc).isoformat()
    execution = plan.setdefault("execution", {})
    execution["approved_by_user"] = args.approved_by
    execution["approved_at"] = approved_at
    if execution.get("level") == "plan_requires_mask_api":
        plan["status"] = "approved_pending_capability"
        manifest["status"] = "approved_pending_capability"
        next_step = "The plan is approved, but local replacement awaits a mask-edit API or a post-production tool."
    else:
        plan["status"] = "approved_for_execution"
        manifest["status"] = "approved_for_execution"
        next_step = "Reuse the existing tl-image or tl-video client task by task, then record each result."
    manifest["approved_at"] = approved_at
    manifest["approved_by"] = args.approved_by
    write_json(run_dir / "plan.json", plan)
    write_json(run_dir / "manifest.json", manifest)
    print(f"Approved Miaodashi run: {run_dir}")
    print(f"Next: {next_step}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
