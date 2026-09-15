#!/usr/bin/env python3
"""Prepare, but never execute, a local FFmpeg concat proposal for approved video clips."""

from __future__ import annotations

import argparse
import json
import shlex
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError) as error:
        raise ValueError(f"cannot read {path.name}: {error}") from error
    if not isinstance(value, dict):
        raise ValueError(f"invalid JSON object: {path.name}")
    return value


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def concat_line(path: Path) -> str:
    return "file " + repr(str(path.resolve()))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Prepare a review-only video assembly proposal without running FFmpeg.")
    parser.add_argument("--run", required=True, help="Path to a Miaodashi video run folder")
    parser.add_argument("--output", help="Proposed final video path; defaults to outputs/final.mp4")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    run_dir = Path(args.run).expanduser()
    try:
        plan = read_json(run_dir / "plan.json")
    except ValueError as error:
        print(f"Error: {error}", file=sys.stderr)
        return 2
    if plan.get("kind") != "video":
        print("Error: prepare_assembly.py only accepts a video run", file=sys.stderr)
        return 2

    clips: list[dict[str, str]] = []
    errors: list[str] = []
    for task in plan.get("tasks", []):
        if task.get("status") != "completed":
            errors.append(f"{task.get('name', '<unnamed>')} is not completed")
            continue
        outputs = task.get("outputs", [])
        if not outputs:
            errors.append(f"{task.get('name', '<unnamed>')} has no recorded output")
            continue
        output = Path(outputs[0]).expanduser()
        if not output.is_file():
            errors.append(f"{task.get('name', '<unnamed>')} output is not a local file: {output}")
            continue
        shot = task.get("shot", {})
        clips.append({"task": str(task.get("name")), "shot_id": str(shot.get("id", "")), "path": str(output.resolve())})
    if errors:
        print("Assembly preflight failed:", file=sys.stderr)
        print("\n".join(f"- {error}" for error in errors), file=sys.stderr)
        return 2
    if not clips:
        print("Error: no completed video clips are available", file=sys.stderr)
        return 2

    output_path = Path(args.output).expanduser() if args.output else run_dir / "outputs" / "final.mp4"
    concat_path = run_dir / "concat.txt"
    concat_path.write_text("\n".join(concat_line(Path(clip["path"])) for clip in clips) + "\n", encoding="utf-8")
    command = ["ffmpeg", "-f", "concat", "-safe", "0", "-i", str(concat_path), "-c", "copy", str(output_path)]
    assembly = {
        "schema_version": 1,
        "format": "miaodashi.video-assembly@1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "mode": "review_only_no_ffmpeg_execution",
        "clips": clips,
        "concat_file": str(concat_path),
        "proposed_output": str(output_path),
        "command": command,
        "shell": shlex.join(command),
        "limitations": [
            "This repository does not execute FFmpeg or verify codec compatibility.",
            "Normalize codecs, add transitions, captions, voiceover, music, brand typography, and final review in an external post-production step.",
            "Use the generated concat command only when every clip is compatible with FFmpeg stream-copy concatenation.",
        ],
    }
    write_json(run_dir / "assemble_plan.json", assembly)
    print(f"Prepared a review-only assembly proposal: {run_dir / 'assemble_plan.json'}")
    print(f"Proposed command: {assembly['shell']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
