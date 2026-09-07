#!/usr/bin/env python3
"""Record an individual TensorsLab generation attempt and its QA outcome."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


QA_KEYS = {"product_truth", "visual_quality", "text_and_rights", "publication_review"}
OUTCOMES = {"completed", "failed", "qa_failed"}


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


def qa_value(value: str) -> tuple[str, str]:
    try:
        key, result = value.split("=", 1)
    except ValueError as error:
        raise argparse.ArgumentTypeError("QA must look like product_truth=pass or visual_quality=fail") from error
    if key not in QA_KEYS or result not in {"pass", "fail", "not_applicable"}:
        raise argparse.ArgumentTypeError("QA keys are product_truth, visual_quality, text_and_rights, publication_review; values are pass, fail, not_applicable")
    return key, result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Record an individual approved Miaodashi task result.")
    parser.add_argument("--run", required=True, help="Path to a run folder")
    parser.add_argument("--task", required=True, help="Exact task name in plan.json")
    parser.add_argument("--status", required=True, choices=sorted(OUTCOMES))
    parser.add_argument("--output", action="append", default=[], help="Output file path or durable output URL; repeatable")
    parser.add_argument("--task-id", help="TensorsLab task id, if supplied by the API")
    parser.add_argument("--note", default="", help="Sanitized error or review note; never include credentials")
    parser.add_argument("--qa", action="append", default=[], type=qa_value, help="Per-task QA result, e.g. product_truth=pass")
    return parser.parse_args()


def overall_status(tasks: list[dict[str, Any]]) -> str:
    statuses = {task.get("status") for task in tasks}
    if statuses == {"completed"}:
        return "completed"
    if statuses & {"failed", "qa_failed"}:
        return "needs_attention"
    return "in_progress"


def main() -> int:
    args = parse_args()
    if args.status == "completed" and not args.output:
        print("Error: completed tasks need at least one --output", file=sys.stderr)
        return 2
    run_dir = Path(args.run).expanduser()
    try:
        plan = read_json(run_dir / "plan.json")
        manifest = read_json(run_dir / "manifest.json")
        qa = read_json(run_dir / "qa.json")
    except ValueError as error:
        print(f"Error: {error}", file=sys.stderr)
        return 2
    if plan.get("status") not in {"approved_for_execution", "in_progress", "needs_attention"}:
        print("Error: record results only after explicit approval for execution", file=sys.stderr)
        return 2
    task = next((item for item in plan.get("tasks", []) if item.get("name") == args.task), None)
    if task is None:
        print("Error: task was not found; use its exact name from plan.json", file=sys.stderr)
        return 2
    now = datetime.now(timezone.utc).isoformat()
    task["status"] = args.status
    if args.output:
        task["outputs"] = args.output
    record = manifest.setdefault("task_status", {}).setdefault(args.task, {"attempts": []})
    record["status"] = args.status
    if args.output:
        record["outputs"] = args.output
    record.setdefault("attempts", []).append(
        {"at": now, "status": args.status, "task_id": args.task_id, "note": args.note, "outputs": args.output}
    )
    for key, result in args.qa:
        record.setdefault("qa", {})[key] = result
        qa.setdefault("checks", {})[key] = result
    if args.status == "qa_failed" or any(result == "fail" for _, result in args.qa):
        qa.setdefault("retry_notes", []).append({"task": args.task, "at": now, "note": args.note or "QA failed; regenerate this task only."})
    manifest["status"] = overall_status(plan["tasks"])
    if manifest["status"] == "completed":
        plan["status"] = "completed"
        qa["status"] = "complete"
    elif manifest["status"] == "needs_attention":
        plan["status"] = "needs_attention"
        qa["status"] = "needs_attention"
    else:
        plan["status"] = "in_progress"
        qa["status"] = "in_progress"
    write_json(run_dir / "plan.json", plan)
    write_json(run_dir / "manifest.json", manifest)
    write_json(run_dir / "qa.json", qa)
    print(f"Recorded {args.status} for task: {args.task}")
    print("Retry only this task if it failed quality review; successful tasks remain untouched.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
