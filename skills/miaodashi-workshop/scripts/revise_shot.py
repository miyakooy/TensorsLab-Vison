#!/usr/bin/env python3
"""Reopen one approved video shot without discarding its prior output record."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from workflow_state import write_json_atomic


def read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError) as error:
        raise ValueError(f"cannot read {path.name}: {error}") from error
    if not isinstance(value, dict):
        raise ValueError(f"invalid JSON object: {path.name}")
    return value


def write_json(path: Path, value: dict[str, Any]) -> None:
    write_json_atomic(path, value)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Reopen one video shot for a deliberate revision; no API call is made.")
    parser.add_argument("--run", required=True, help="Path to a Miaodashi run folder")
    parser.add_argument("--task", required=True, help="Exact shot task name in plan.json")
    parser.add_argument("--reason", required=True, help="Why this shot needs a new attempt")
    parser.add_argument("--prompt", help="Replacement prompt; otherwise keep the current prompt")
    parser.add_argument(
        "--replace-approved",
        action="store_true",
        help="Required when reopening a completed shot; preserves its old outputs in previous_outputs.",
    )
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
    if plan.get("kind") != "video":
        print("Error: revise_shot.py is only for a video run", file=sys.stderr)
        return 2
    if plan.get("status") not in {"approved_for_execution", "in_progress", "needs_attention", "completed"}:
        print("Error: approve the video plan before reopening a shot", file=sys.stderr)
        return 2
    task = next((item for item in plan.get("tasks", []) if item.get("name") == args.task), None)
    if task is None:
        print("Error: task was not found; use its exact name from plan.json", file=sys.stderr)
        return 2
    if task.get("status") == "completed" and not args.replace_approved:
        print("Error: completed shots need --replace-approved to preserve their approved output history", file=sys.stderr)
        return 2
    now = datetime.now(timezone.utc).isoformat()
    previous_outputs = task.get("outputs", [])
    if previous_outputs:
        task.setdefault("previous_outputs", []).append({"at": now, "reason": args.reason, "outputs": previous_outputs})
        task["outputs"] = []
    if args.prompt is not None:
        task["prompt"] = args.prompt
    task["status"] = "needs_approval"
    task["qa_status"] = "pending"
    task["delivery_status"] = "blocked"
    approval = plan.setdefault("execution", {}).get("approval", {})
    approval.get("task_digests", {}).pop(args.task, None)
    record = manifest.setdefault("task_status", {}).setdefault(args.task, {"attempts": []})
    record["status"] = "needs_approval"
    record["approval_status"] = "needs_approval"
    record.pop("approval_digest", None)
    record.setdefault("revisions", []).append({"at": now, "reason": args.reason, "replaced_approved_output": bool(previous_outputs)})
    record.setdefault("attempts", []).append({"at": now, "status": "reopened", "note": args.reason, "outputs": []})
    plan["status"] = "needs_approval"
    manifest["status"] = "needs_approval"
    write_json(run_dir / "plan.json", plan)
    write_json(run_dir / "manifest.json", manifest)
    print(f"Reopened shot for a new attempt: {args.task}")
    print("Next: explicitly approve this revised task, then prepare its dispatch command.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
