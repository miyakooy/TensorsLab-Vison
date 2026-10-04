"""Shared approval and state helpers for the local workshop workflow."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from copy import deepcopy
from pathlib import Path
from typing import Any, Iterable


APPROVAL_FORMAT = "miaodashi.execution-approval@1"
APPROVAL_PARAMETER_KEYS = (
    "model",
    "image_resolution",
    "video_ratio",
    "video_duration",
    "video_resolution",
)
QA_KEYS = ("product_truth", "visual_quality", "text_and_rights", "publication_review")
QA_PASS_VALUES = {"pass", "not_applicable"}


def write_json_atomic(path: Path, value: object) -> None:
    """Replace a JSON file atomically so an interrupted write cannot truncate it."""
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    temporary_path = Path(temporary)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(value, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_path, path)
    except BaseException:
        temporary_path.unlink(missing_ok=True)
        raise


def approved_parameters(values: Any) -> dict[str, Any]:
    """Return the output-affecting dispatch overrides from a namespace or mapping."""
    if isinstance(values, dict):
        return {key: values.get(key) for key in APPROVAL_PARAMETER_KEYS}
    return {key: getattr(values, key, None) for key in APPROVAL_PARAMETER_KEYS}


def _asset_paths(value: Any) -> Iterable[Path]:
    if isinstance(value, dict):
        if value.get("type") == "local" and isinstance(value.get("value"), str):
            yield Path(value["value"]).expanduser()
        for key, child in value.items():
            if key in {"product_file", "csv"} and isinstance(child, str):
                yield Path(child).expanduser()
            elif key not in {"value", "product_file", "csv", "asset_directory"}:
                yield from _asset_paths(child)
    elif isinstance(value, list):
        for child in value:
            yield from _asset_paths(child)


def asset_fingerprints(plan: dict[str, Any], task: dict[str, Any]) -> dict[str, str]:
    """Hash local inputs that can affect one task's generated output."""
    sources = {
        path.resolve()
        for path in _asset_paths(
            {
                "asset_roles": plan.get("asset_roles"),
                "batch_sku": plan.get("batch_sku"),
                "task": task,
            }
        )
        if path.is_file()
    }
    return {
        str(path): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(sources, key=lambda item: str(item))
    }


def _task_payload(task: dict[str, Any]) -> dict[str, Any]:
    payload = deepcopy(task)
    for key in (
        "status",
        "outputs",
        "previous_outputs",
        "generation_status",
        "qa_status",
        "delivery_status",
    ):
        payload.pop(key, None)
    return payload


def _shared_payload(plan: dict[str, Any], parameters: dict[str, Any]) -> dict[str, Any]:
    execution = plan.get("execution", {})
    return {
        "schema_version": plan.get("schema_version"),
        "project": plan.get("project"),
        "scenario": plan.get("scenario"),
        "requested_scenario": plan.get("requested_scenario"),
        "kind": plan.get("kind"),
        "platform": plan.get("platform"),
        "asset_roles": plan.get("asset_roles"),
        "constraints": plan.get("constraints"),
        "batch_sku": plan.get("batch_sku"),
        "video_story": plan.get("video_story"),
        "execution": {
            "skill": execution.get("skill"),
            "reference": execution.get("reference"),
            "level": execution.get("level"),
            "parameters": parameters,
        },
    }


def task_approval_digest(
    plan: dict[str, Any], task: dict[str, Any], parameters: dict[str, Any]
) -> str:
    payload = {
        "format": APPROVAL_FORMAT,
        "shared": _shared_payload(plan, parameters),
        "task": _task_payload(task),
        "assets": asset_fingerprints(plan, task),
    }
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def approval_errors(
    plan: dict[str, Any], tasks: Iterable[dict[str, Any]], parameters: dict[str, Any]
) -> list[str]:
    approval = plan.get("execution", {}).get("approval")
    if not isinstance(approval, dict) or approval.get("format") != APPROVAL_FORMAT:
        return ["the run has no verifiable execution approval; approve it again"]
    if approval.get("parameters") != parameters:
        return ["dispatch parameters differ from the approved model or output settings"]
    recorded = approval.get("task_digests", {})
    errors: list[str] = []
    for task in tasks:
        name = str(task.get("name", "<unnamed>"))
        expected = recorded.get(name)
        current = task_approval_digest(plan, task, parameters)
        if expected is None:
            errors.append(f"{name}: task has not been approved")
        elif expected != current:
            errors.append(f"{name}: approved content, parameters, or source assets changed; approve it again")
    return errors


def qa_status(checks: dict[str, str]) -> str:
    if any(checks.get(key) == "fail" for key in QA_KEYS):
        return "failed"
    if all(checks.get(key) in QA_PASS_VALUES for key in QA_KEYS):
        return "passed"
    return "pending"
