"""Durable local task records for a standalone TensorsLab client."""

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional


TASK_RECORD_FORMAT = "tensorslab.task@1"
DEFAULT_STATE_DIR = Path(".") / ".tensorslab_tasks"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _record_name(record_id: str) -> str:
    readable = re.sub(r"[^A-Za-z0-9._-]+", "-", record_id).strip("-._")[:64] or "task"
    suffix = hashlib.sha256(record_id.encode("utf-8")).hexdigest()[:10]
    return f"{readable}-{suffix}.json"


def record_path(state_dir: Path, record_id: str) -> Path:
    return state_dir.expanduser() / _record_name(record_id)


def write_json_atomic(path: Path, value: object) -> None:
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


def new_task_record(
    *,
    kind: str,
    task_id: Optional[str],
    request: dict[str, Any],
    output_dir: Path,
    submission_status: str = "accepted",
) -> dict[str, Any]:
    created_at = utc_now()
    record_id = task_id or "submission_unknown-" + hashlib.sha256(
        json.dumps(request, sort_keys=True, ensure_ascii=False).encode("utf-8") + created_at.encode("utf-8")
    ).hexdigest()[:16]
    return {
        "format": TASK_RECORD_FORMAT,
        "record_id": record_id,
        "kind": kind,
        "task_id": task_id,
        "submission_status": submission_status,
        "generation_status": "submitted" if task_id else "submission_unknown",
        "download_status": "not_started",
        "request": request,
        "output_dir": str(output_dir.expanduser().resolve()),
        "result_urls": [],
        "outputs": [],
        "error": None,
        "created_at": created_at,
        "updated_at": created_at,
    }


def save_task_record(state_dir: Path, record: dict[str, Any]) -> Path:
    record["updated_at"] = utc_now()
    path = record_path(state_dir, str(record["record_id"]))
    write_json_atomic(path, record)
    return path


def load_task_record(state_dir: Path, task_id: str) -> Optional[dict[str, Any]]:
    path = record_path(state_dir, task_id)
    if not path.is_file():
        return None
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict) or value.get("format") != TASK_RECORD_FORMAT:
        raise ValueError(f"invalid task record: {path}")
    return value


def operation_result(record: dict[str, Any], operation: str, path: Path) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "kind": record.get("kind"),
        "operation": operation,
        "task_id": record.get("task_id"),
        "submission_status": record.get("submission_status"),
        "generation_status": record.get("generation_status"),
        "download_status": record.get("download_status"),
        "result_urls": record.get("result_urls", []),
        "outputs": record.get("outputs", []),
        "error": record.get("error"),
        "next_action": record.get("next_action"),
        "record_path": str(path.resolve()),
    }
