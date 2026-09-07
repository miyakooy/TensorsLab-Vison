#!/usr/bin/env python3
"""Validate an approved run and prepare exact existing-client commands.

The script never submits an API request. It emits a local ``dispatch.json``
with one command per eligible task so a user or agent can review the exact
TensorsLab client invocation before billable execution.
"""

from __future__ import annotations

import argparse
import json
import shlex
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


RUNNABLE_PLAN_STATUSES = {"approved_for_execution", "in_progress", "needs_attention"}
RUNNABLE_TASK_STATUSES = {"planned", "failed", "qa_failed"}
DIRECT_EXECUTION_LEVELS = {"direct_api", "direct_api_with_review", "direct_api_after_sample"}


def read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise ValueError(f"missing run file: {path.name}") from error
    except json.JSONDecodeError as error:
        raise ValueError(f"invalid JSON in {path.name}: {error.msg}") from error
    if not isinstance(value, dict):
        raise ValueError(f"invalid JSON object: {path.name}")
    return value


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Preflight an approved Miaodashi run and prepare existing TensorsLab client commands without calling the API."
    )
    parser.add_argument("--run", required=True, help="Path to a run folder")
    parser.add_argument("--task", action="append", default=[], help="Exact task name to prepare; repeatable")
    parser.add_argument("--model", help="Optional model override passed to the existing TensorsLab client")
    parser.add_argument("--image-resolution", help="Optional image resolution passed to tl-image")
    parser.add_argument("--video-ratio", help="Optional video ratio passed to tl-video")
    parser.add_argument("--video-duration", type=int, help="Optional video duration passed to tl-video")
    parser.add_argument("--video-resolution", help="Optional video resolution passed to tl-video")
    parser.add_argument("--timeout", type=int, help="Optional client timeout in seconds")
    return parser.parse_args()


def asset_values(records: list[dict[str, Any]], *, allow_urls: bool) -> tuple[list[str], list[str], list[str]]:
    """Return local paths, URLs, and validation errors for a source-role list."""
    local_paths: list[str] = []
    urls: list[str] = []
    errors: list[str] = []
    for record in records:
        value = record.get("value")
        role = record.get("role", "asset")
        if not isinstance(value, str) or not value:
            errors.append(f"{role} has no usable value")
            continue
        if record.get("type") == "url":
            if allow_urls:
                urls.append(value)
            else:
                errors.append(f"{role} URL cannot be passed to this client")
        elif Path(value).is_file():
            local_paths.append(value)
        else:
            errors.append(f"{role} is missing locally: {value}")
    return local_paths, urls, errors


def image_sources(plan: dict[str, Any], task: dict[str, Any]) -> tuple[list[str], list[str], list[str]]:
    asset_roles = plan.get("asset_roles", {})
    primary = asset_roles.get("primary_sources", [])
    references = asset_roles.get("visual_references", [])
    scenario = plan.get("scenario")
    if scenario == "batch-sku":
        template = plan.get("batch_sku", {}).get("template")
        records = [
            {"type": "local", "value": task.get("product_file"), "role": "SKU product"},
            template or {"role": "approved template"},
        ]
    elif scenario == "phone-retouch":
        task_source = task.get("input_assets", [])
        records = task_source or primary
    elif scenario == "format-adaptation":
        task_source = task.get("input_assets", [])
        records = task_source or primary
    else:
        records = [*primary, *references]
    local_paths, urls, errors = asset_values(records, allow_urls=True)
    if len(urls) > 1:
        errors.append("tl-image supports one --image-url per task; replace extra remote sources with local files")
    return local_paths, urls, errors


def video_sources(plan: dict[str, Any], task: dict[str, Any]) -> tuple[list[str], list[str], list[str]]:
    primary = plan.get("asset_roles", {}).get("primary_sources", [])
    records = task.get("input_assets", []) or primary
    local_paths, urls, errors = asset_values(records, allow_urls=True)
    if len(local_paths) > 2:
        errors.append("tl-video supports at most two local --source images per task")
    if len(urls) > 1:
        errors.append("tl-video supports one --image-url per task; replace extra remote sources with local files")
    return local_paths, urls, errors


def client_path(kind: str) -> Path:
    skills_root = Path(__file__).resolve().parents[2]
    if kind == "image":
        return skills_root / "tl-image" / "scripts" / "tensorslab_image.py"
    if kind == "video":
        return skills_root / "tl-video" / "scripts" / "tensorslab_video.py"
    raise ValueError(f"unsupported run kind: {kind}")


def command_for_task(plan: dict[str, Any], task: dict[str, Any], args: argparse.Namespace, run_dir: Path) -> tuple[list[str], list[str]]:
    kind = plan.get("kind")
    prompt = task.get("prompt")
    if not isinstance(prompt, str) or not prompt.strip():
        return [], [f"task {task.get('name', '<unnamed>')} has no approved prompt"]
    if kind == "image":
        local_paths, urls, errors = image_sources(plan, task)
    else:
        local_paths, urls, errors = video_sources(plan, task)
    if errors:
        return [], errors

    command = [sys.executable, str(client_path(kind)), prompt, "--output-dir", str(run_dir / "outputs")]
    for source in local_paths:
        command.extend(["--source", source])
    if urls:
        command.extend(["--image-url", urls[0]])
    if args.model:
        command.extend(["--model", args.model])
    if args.timeout:
        command.extend(["--timeout", str(args.timeout)])
    if kind == "image" and args.image_resolution:
        command.extend(["--resolution", args.image_resolution])
    if kind == "video":
        if args.video_ratio:
            command.extend(["--ratio", args.video_ratio])
        if args.video_duration:
            command.extend(["--duration", str(args.video_duration)])
        if args.video_resolution:
            command.extend(["--resolution", args.video_resolution])
    return command, []


def selected_tasks(plan: dict[str, Any], requested_names: list[str]) -> list[dict[str, Any]]:
    tasks = plan.get("tasks", [])
    if not requested_names:
        return [task for task in tasks if task.get("status") in RUNNABLE_TASK_STATUSES]
    requested = set(requested_names)
    found = {task.get("name") for task in tasks if task.get("name") in requested}
    missing = requested - found
    if missing:
        raise ValueError("task was not found: " + ", ".join(sorted(missing)))
    return [task for task in tasks if task.get("name") in requested]


def main() -> int:
    args = parse_args()
    run_dir = Path(args.run).expanduser()
    try:
        plan = read_json(run_dir / "plan.json")
    except ValueError as error:
        print(f"Error: {error}", file=sys.stderr)
        return 2
    if plan.get("status") not in RUNNABLE_PLAN_STATUSES:
        print("Error: approve the run for execution before preparing dispatch commands", file=sys.stderr)
        return 2
    execution = plan.get("execution", {})
    if execution.get("level") not in DIRECT_EXECUTION_LEVELS:
        print("Error: this run needs an unavailable API capability or a post-production handoff", file=sys.stderr)
        return 2
    try:
        tasks = selected_tasks(plan, args.task)
    except ValueError as error:
        print(f"Error: {error}", file=sys.stderr)
        return 2
    if not tasks:
        print("Error: this run has no planned, failed, or qa_failed tasks to dispatch", file=sys.stderr)
        return 2

    prepared: list[dict[str, Any]] = []
    errors: list[str] = []
    for task in tasks:
        command, task_errors = command_for_task(plan, task, args, run_dir)
        if task_errors:
            errors.extend(f"{task.get('name', '<unnamed>')}: {error}" for error in task_errors)
            continue
        prepared.append({"task": task["name"], "status": task["status"], "command": command, "shell": shlex.join(command)})
    if errors:
        print("Preflight failed:", file=sys.stderr)
        print("\n".join(f"- {error}" for error in errors), file=sys.stderr)
        return 2

    dispatch = {
        "schema_version": 1,
        "project": plan.get("project"),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "mode": "review_only_no_api_call",
        "run_status": plan.get("status"),
        "client": execution.get("skill"),
        "commands": prepared,
        "next_step": "Review these commands, then invoke the existing TensorsLab client manually for each task and record the result with record_result.py.",
    }
    write_json(run_dir / "dispatch.json", dispatch)
    print(f"Prepared {len(prepared)} review-only dispatch command(s): {run_dir / 'dispatch.json'}")
    for item in prepared:
        print(f"- {item['task']}: {item['shell']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
