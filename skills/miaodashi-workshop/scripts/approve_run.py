#!/usr/bin/env python3
"""Move a completed local Miaodashi plan to explicit user approval."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from workflow_state import (
    APPROVAL_FORMAT,
    approved_parameters,
    task_approval_digest,
    write_json_atomic,
)


def read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise ValueError(f"missing run file: {path.name}") from error
    if not isinstance(value, dict):
        raise ValueError(f"invalid JSON object: {path.name}")
    return value


def write_json(path: Path, value: dict[str, Any]) -> None:
    write_json_atomic(path, value)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Record explicit approval for a filled Miaodashi plan.")
    parser.add_argument("--run", required=True, help="Path to a run folder containing plan.json")
    parser.add_argument("--approved-by", required=True, help="Person or approval reference supplied by the user")
    parser.add_argument("--task", action="append", default=[], help="Approve only this revised task; repeatable")
    parser.add_argument("--model", help="Approved model override for subsequent dispatch")
    parser.add_argument("--image-resolution", help="Approved image resolution override")
    parser.add_argument("--video-ratio", help="Approved video ratio override")
    parser.add_argument("--video-duration", type=int, help="Approved video duration override")
    parser.add_argument("--video-resolution", help="Approved video resolution override")
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

    approvable_statuses = {
        "draft_needs_approval", "approved_for_execution", "in_progress",
        "needs_attention", "review_pending", "needs_approval", "completed",
    }
    if plan.get("status") not in approvable_statuses:
        print("Error: this run is not in an approvable state", file=sys.stderr)
        return 2
    constraints = plan.get("constraints", {})
    missing = []
    if not constraints.get("immutable_facts"):
        missing.append("constraints.immutable_facts")
    if not constraints.get("brand_anchors"):
        missing.append("constraints.brand_anchors")
    all_tasks = plan.get("tasks", [])
    requested = set(args.task)
    selected = [task for task in all_tasks if not requested or task.get("name") in requested]
    found = {task.get("name") for task in selected}
    if requested - found:
        missing.append("requested task(s): " + ", ".join(sorted(requested - found)))
    if not selected or any(not task.get("prompt", "").strip() for task in selected):
        missing.append("a non-empty prompt for every selected task")
    if missing:
        print("Error: complete " + ", ".join(missing) + " before approval", file=sys.stderr)
        return 2

    approved_at = datetime.now(timezone.utc).isoformat()
    execution = plan.setdefault("execution", {})
    existing_approval = execution.get("approval", {})
    parameters = approved_parameters(args)
    existing_parameters = existing_approval.get("parameters")
    if isinstance(existing_parameters, dict):
        parameters = {
            key: value if value is not None else existing_parameters.get(key)
            for key, value in parameters.items()
        }
    if requested:
        if not isinstance(existing_parameters, dict):
            print("Error: task-only approval requires an existing full-plan approval", file=sys.stderr)
            return 2
        supplied_parameters = approved_parameters(args)
        supplied = {key: value for key, value in supplied_parameters.items() if value is not None}
        conflicts = {key for key, value in supplied.items() if existing_parameters.get(key) != value}
        if conflicts:
            print("Error: task-only approval cannot change global dispatch parameters; approve the full plan", file=sys.stderr)
            return 2
        parameters = existing_parameters
    task_digests = dict(existing_approval.get("task_digests", {})) if requested else {}
    for task in selected:
        digest = task_approval_digest(plan, task, parameters)
        task_digests[str(task["name"])] = digest
        if task.get("status") == "needs_approval":
            task["status"] = "planned"
        record = manifest.setdefault("task_status", {}).setdefault(task["name"], {"attempts": []})
        record["approval_status"] = "approved"
        record["approval_digest"] = digest
        record["approved_at"] = approved_at
        record["approved_by"] = args.approved_by
    execution["approval"] = {
        "format": APPROVAL_FORMAT,
        "approved_by": args.approved_by,
        "approved_at": approved_at,
        "parameters": parameters,
        "task_digests": task_digests,
    }
    execution["approved_by_user"] = args.approved_by
    execution["approved_at"] = approved_at
    if execution.get("level") == "plan_requires_mask_api":
        plan["status"] = "approved_pending_capability"
        manifest["status"] = "approved_pending_capability"
        next_step = "The plan is approved, but local replacement awaits a mask-edit API or a post-production tool."
    else:
        plan["status"] = "in_progress" if requested else "approved_for_execution"
        manifest["status"] = plan["status"]
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
