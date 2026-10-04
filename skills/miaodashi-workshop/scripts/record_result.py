#!/usr/bin/env python3
"""Record an individual TensorsLab generation attempt and its QA outcome."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from workflow_state import QA_KEYS, approval_errors, qa_status, write_json_atomic

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
    write_json_atomic(path, value)


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
    parser.add_argument(
        "--replace-approved",
        action="store_true",
        help="Required to replace the current output record of a completed task.",
    )
    parser.add_argument("--qa", action="append", default=[], type=qa_value, help="Per-task QA result, e.g. product_truth=pass")
    return parser.parse_args()


def overall_status(tasks: list[dict[str, Any]]) -> str:
    statuses = {task.get("status") for task in tasks}
    if tasks and all(task.get("delivery_status") == "ready" for task in tasks):
        return "completed"
    if statuses & {"failed", "qa_failed"}:
        return "needs_attention"
    if "needs_approval" in statuses:
        return "needs_approval"
    if statuses <= {"completed", "qa_pending"}:
        return "review_pending"
    return "in_progress"


def aggregate_checks(tasks: list[dict[str, Any]], qa_tasks: dict[str, Any]) -> dict[str, str]:
    aggregated: dict[str, str] = {}
    for key in QA_KEYS:
        values = [qa_tasks.get(str(task.get("name")), {}).get(key, "pending") for task in tasks]
        if "fail" in values:
            aggregated[key] = "fail"
        elif values and all(value in {"pass", "not_applicable"} for value in values):
            aggregated[key] = "pass"
        else:
            aggregated[key] = "pending"
    return aggregated


def main() -> int:
    args = parse_args()
    run_dir = Path(args.run).expanduser()
    try:
        plan = read_json(run_dir / "plan.json")
        manifest = read_json(run_dir / "manifest.json")
        qa = read_json(run_dir / "qa.json")
    except ValueError as error:
        print(f"Error: {error}", file=sys.stderr)
        return 2
    if plan.get("status") not in {
        "approved_for_execution", "in_progress", "needs_attention", "review_pending", "needs_approval"
    }:
        print("Error: record results only after explicit approval for execution", file=sys.stderr)
        return 2
    task = next((item for item in plan.get("tasks", []) if item.get("name") == args.task), None)
    if task is None:
        print("Error: task was not found; use its exact name from plan.json", file=sys.stderr)
        return 2
    approval = plan.get("execution", {}).get("approval", {})
    approval_problem = approval_errors(plan, [task], approval.get("parameters", {}))
    if approval_problem:
        print("Error: result cannot be recorded for an unapproved or changed task", file=sys.stderr)
        print("\n".join(f"- {error}" for error in approval_problem), file=sys.stderr)
        return 2
    existing_outputs = task.get("outputs", [])
    if args.status == "completed" and not args.output and not existing_outputs:
        print("Error: completed tasks need at least one --output", file=sys.stderr)
        return 2
    replacing_outputs = bool(args.output and args.output != existing_outputs)
    if task.get("delivery_status") == "ready" and replacing_outputs and not args.replace_approved:
        print("Error: use revise_shot.py or --replace-approved before replacing a delivery-ready output", file=sys.stderr)
        return 2
    now = datetime.now(timezone.utc).isoformat()
    if args.output:
        task["outputs"] = args.output
    record = manifest.setdefault("task_status", {}).setdefault(args.task, {"attempts": []})
    if args.output:
        record["outputs"] = args.output
    record.setdefault("attempts", []).append(
        {"at": now, "status": args.status, "task_id": args.task_id, "note": args.note, "outputs": args.output}
    )
    task_checks = record.setdefault("qa", {})
    for key, result in args.qa:
        task_checks[key] = result
    if args.status == "qa_failed" and not any(value == "fail" for value in task_checks.values()):
        print("Error: qa_failed requires at least one --qa check marked fail", file=sys.stderr)
        return 2
    current_qa_status = qa_status(task_checks)
    generation_status = "failed" if args.status == "failed" else "completed"
    if args.status == "qa_failed":
        current_qa_status = "failed"
    delivery_status = "ready" if generation_status == "completed" and current_qa_status == "passed" else "blocked"
    if generation_status == "failed":
        task_status = "failed"
    elif current_qa_status == "failed":
        task_status = "qa_failed"
    elif delivery_status == "ready":
        task_status = "completed"
    else:
        task_status = "qa_pending"
    task["status"] = task_status
    task["generation_status"] = generation_status
    task["qa_status"] = current_qa_status
    task["delivery_status"] = delivery_status
    record["status"] = task_status
    record["generation_status"] = generation_status
    record["qa_status"] = current_qa_status
    record["delivery_status"] = delivery_status
    qa_tasks = qa.setdefault("tasks", {})
    qa_tasks[args.task] = dict(task_checks)
    qa["checks"] = aggregate_checks(plan["tasks"], qa_tasks)
    if current_qa_status == "failed":
        qa.setdefault("retry_notes", []).append({"task": args.task, "at": now, "note": args.note or "QA failed; regenerate this task only."})
    manifest["status"] = overall_status(plan["tasks"])
    if manifest["status"] == "completed":
        plan["status"] = "completed"
        qa["status"] = "complete"
    elif manifest["status"] == "needs_attention":
        plan["status"] = "needs_attention"
        qa["status"] = "needs_attention"
    elif manifest["status"] == "review_pending":
        plan["status"] = "review_pending"
        qa["status"] = "pending"
    elif manifest["status"] == "needs_approval":
        plan["status"] = "needs_approval"
        qa["status"] = "pending"
    else:
        plan["status"] = "in_progress"
        qa["status"] = "in_progress"
    write_json(run_dir / "plan.json", plan)
    write_json(run_dir / "manifest.json", manifest)
    write_json(run_dir / "qa.json", qa)
    print(f"Recorded {generation_status} generation and {current_qa_status} QA for task: {args.task}")
    print(f"Delivery status: {delivery_status}")
    print("Retry only this task if it failed quality review; successful tasks remain untouched.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
