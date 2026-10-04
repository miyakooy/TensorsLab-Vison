from __future__ import annotations

import io
import json
import importlib.util
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
IMAGE_CLIENT = ROOT / "skills/tl-image/scripts/tensorslab_image.py"
VIDEO_CLIENT = ROOT / "skills/tl-video/scripts/tensorslab_video.py"
WORKSHOP = ROOT / "skills/miaodashi-workshop/scripts"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FakeResponse:
    status_code = 200
    text = '{"code":1000}'

    def json(self) -> dict:
        return {"code": 1000, "data": {"taskid": "task_test_123"}}


class MissingTaskIdResponse(FakeResponse):
    def json(self) -> dict:
        return {"code": 1000, "data": {}}


class FakeSession:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def post(self, endpoint: str, **kwargs) -> FakeResponse:
        self.calls.append({"endpoint": endpoint, **kwargs})
        return FakeResponse()


def run_cli(*args: object, expected: int = 0) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        [sys.executable, *(str(arg) for arg in args)],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != expected:
        raise AssertionError(
            f"expected exit {expected}, got {result.returncode}\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )
    return result


class ClientSmokeTests(unittest.TestCase):
    def test_success_response_without_task_id_is_submission_unknown(self) -> None:
        module = load_module("tensorslab_image_missing_task_id_test", IMAGE_CLIENT)
        fake = FakeSession()
        fake.post = mock.Mock(return_value=MissingTaskIdResponse())
        module._SESSION = fake
        with self.assertRaises(module.TensorsLabSubmissionUnknown):
            module.generate_image("approved product image", api_key="test-key")

    def test_image_submit_persists_task_before_waiting(self) -> None:
        module = load_module("tensorslab_image_submit_state_test", IMAGE_CLIENT)
        with tempfile.TemporaryDirectory() as temp_dir:
            state_dir = Path(temp_dir) / "state"
            stdout = io.StringIO()
            argv = [
                str(IMAGE_CLIENT), "approved product image",
                "--operation", "submit",
                "--state-dir", str(state_dir),
                "--api-key", "test-key",
            ]
            with mock.patch.object(module, "generate_image", return_value="task_persisted_123"):
                with mock.patch.object(sys, "argv", argv), redirect_stdout(stdout):
                    self.assertEqual(module.main(), 0)
            result = json.loads(stdout.getvalue())
            self.assertEqual(result["task_id"], "task_persisted_123")
            self.assertEqual(result["generation_status"], "submitted")
            record = json.loads(Path(result["record_path"]).read_text(encoding="utf-8"))
            self.assertEqual(record["submission_status"], "accepted")
            self.assertNotIn("api_key", json.dumps(record))

    def test_unknown_submission_is_recorded_without_retry(self) -> None:
        module = load_module("tensorslab_image_unknown_state_test", IMAGE_CLIENT)
        with tempfile.TemporaryDirectory() as temp_dir:
            state_dir = Path(temp_dir) / "state"
            stdout = io.StringIO()
            argv = [
                str(IMAGE_CLIENT), "approved product image",
                "--operation", "submit",
                "--state-dir", str(state_dir),
                "--api-key", "test-key",
            ]
            failure = module.TensorsLabSubmissionUnknown("connection closed after submit")
            with mock.patch.object(module, "generate_image", side_effect=failure) as submit:
                with mock.patch.object(sys, "argv", argv), redirect_stdout(stdout):
                    self.assertEqual(module.main(), 1)
            submit.assert_called_once()
            result = json.loads(stdout.getvalue())
            self.assertIsNone(result["task_id"])
            self.assertEqual(result["generation_status"], "submission_unknown")
            self.assertEqual(result["error"]["code"], "SUBMISSION_UNKNOWN")
            self.assertTrue(Path(result["record_path"]).is_file())

    def test_video_status_reads_existing_task_without_submitting(self) -> None:
        module = load_module("tensorslab_video_status_state_test", VIDEO_CLIENT)
        with tempfile.TemporaryDirectory() as temp_dir:
            state_dir = Path(temp_dir) / "state"
            stdout = io.StringIO()
            argv = [
                str(VIDEO_CLIENT),
                "--operation", "status",
                "--task-id", "video_existing_123",
                "--state-dir", str(state_dir),
                "--api-key", "test-key",
            ]
            status = {"task_status": 3, "url": ["https://example.com/result.mp4"]}
            with mock.patch.object(module, "query_task_status", return_value=status):
                with mock.patch.object(module, "generate_video") as submit:
                    with mock.patch.object(sys, "argv", argv), redirect_stdout(stdout):
                        self.assertEqual(module.main(), 0)
            submit.assert_not_called()
            result = json.loads(stdout.getvalue())
            self.assertEqual(result["generation_status"], "completed")
            self.assertEqual(result["next_action"], "download")

    def test_image_download_resumes_without_submitting(self) -> None:
        module = load_module("tensorslab_image_download_resume_test", IMAGE_CLIENT)
        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            state_dir = temp / "state"
            output_dir = temp / "output"
            downloaded = output_dir / "task_existing_0.png"
            status = {"image_status": 3, "url": ["https://example.com/result.png"]}
            stdout = io.StringIO()
            argv = [
                str(IMAGE_CLIENT),
                "--operation", "download",
                "--task-id", "task_existing",
                "--state-dir", str(state_dir),
                "--output-dir", str(output_dir),
                "--api-key", "test-key",
            ]
            with mock.patch.object(module, "query_task_status", return_value=status):
                with mock.patch.object(module, "download_task_outputs", return_value=[str(downloaded)]):
                    with mock.patch.object(module, "generate_image") as submit:
                        with mock.patch.object(sys, "argv", argv), redirect_stdout(stdout):
                            self.assertEqual(module.main(), 0)
            submit.assert_not_called()
            result = json.loads(stdout.getvalue())
            self.assertEqual(result["download_status"], "completed")
            self.assertEqual(result["outputs"], [str(downloaded.resolve())])

    def test_image_submit_builds_documented_multipart_fields(self) -> None:
        module = load_module("tensorslab_image_test", IMAGE_CLIENT)
        fake = FakeSession()
        module._SESSION = fake
        task_id = module.generate_image(
            "studio cup",
            model="seedreamv45",
            resolution="4:5",
            batch_size=2,
            api_key="test-key",
        )
        self.assertEqual(task_id, "task_test_123")
        fields = {name: value[1] for name, value in fake.calls[0]["files"]}
        self.assertEqual(fields["batchsize"], "2")
        self.assertEqual(fields["category"], "seedreamv45")

    def test_image_dry_run_needs_no_key(self) -> None:
        result = run_cli(
            IMAGE_CLIENT,
            "studio product photo of a ceramic cup",
            "--model",
            "seedreamv45",
            "--resolution",
            "4:5",
            "--batch-size",
            3,
            "--dry-run",
        )
        payload = json.loads(result.stdout)
        self.assertEqual(payload["batch_size"], 3)
        self.assertEqual(payload["endpoint"], "https://api.tensorslab.com/v1/images/seedreamv45")
        self.assertFalse(payload["submits_request"])

    def test_seedream_v5_uses_its_documented_endpoint(self) -> None:
        module = load_module("tensorslab_image_v5_test", IMAGE_CLIENT)
        fake = FakeSession()
        module._SESSION = fake
        module.generate_image(
            "premium product hero",
            model="seedreamv5",
            resolution="2K",
            batch_size=2,
            api_key="test-key",
        )
        fields = {name: value[1] for name, value in fake.calls[0]["files"]}
        self.assertEqual(fake.calls[0]["endpoint"], "https://api.tensorslab.com/v1/images/seedreamv5")
        self.assertEqual(fields["category"], "seedreamv5")
        self.assertEqual(fields["batchsize"], "2")

    def test_zimage_uses_documented_default_resolution(self) -> None:
        result = run_cli(IMAGE_CLIENT, "ink illustration", "--model", "zimage", "--dry-run")
        self.assertEqual(json.loads(result.stdout)["resolution"], "1024*1024")

    def test_video_rejects_v2_only_options_on_v1(self) -> None:
        result = run_cli(
            VIDEO_CLIENT,
            "slow camera orbit around a product",
            "--model",
            "seedancev1profast",
            "--audio",
            "--dry-run",
            expected=1,
        )
        self.assertIn("only on seedancev2", result.stderr)

    def test_video_dry_run_needs_no_key(self) -> None:
        result = run_cli(
            VIDEO_CLIENT,
            "slow camera orbit around a product",
            "--model",
            "seedancev2",
            "--duration",
            10,
            "--resolution",
            "1080p",
            "--audio",
            "--dry-run",
        )
        payload = json.loads(result.stdout)
        self.assertTrue(payload["generate_audio"])
        self.assertFalse(payload["submits_request"])

    def test_video_submit_builds_documented_multipart_fields(self) -> None:
        module = load_module("tensorslab_video_test", VIDEO_CLIENT)
        fake = FakeSession()
        module._SESSION = fake
        task_id = module.generate_video(
            "slow product orbit",
            model="seedancev2",
            duration=10,
            resolution="1080p",
            generate_audio=True,
            api_key="test-key",
        )
        self.assertEqual(task_id, "task_test_123")
        fields = {name: value[1] for name, value in fake.calls[0]["files"]}
        self.assertEqual(fields["duration"], "10")
        self.assertEqual(fields["generate_audio"], "1")


class WorkshopSmokeTests(unittest.TestCase):
    def test_plan_approval_dispatch_and_result_recording(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            source = temp / "product.jpg"
            source.write_bytes(b"test fixture")
            output_root = temp / "runs"

            run_cli(
                WORKSHOP / "create_run.py",
                "--project",
                "cup-launch",
                "--scenario",
                "listing-kit",
                "--source",
                source,
                "--output-count",
                1,
                "--output-dir",
                output_root,
            )
            run_dir = output_root / "cup-launch"
            plan_path = run_dir / "plan.json"
            plan = json.loads(plan_path.read_text(encoding="utf-8"))
            plan["constraints"]["immutable_facts"] = ["white ceramic cup"]
            plan["constraints"]["brand_anchors"] = ["warm daylight"]
            plan["tasks"][0]["prompt"] = "Keep the white ceramic cup unchanged on a warm studio set."
            plan_path.write_text(json.dumps(plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

            run_cli(
                WORKSHOP / "approve_run.py",
                "--run", run_dir,
                "--approved-by", "test-user",
                "--model", "seedreamv45",
                "--image-resolution", "4:5",
            )
            run_cli(
                WORKSHOP / "prepare_dispatch.py",
                "--run",
                run_dir,
                "--model",
                "seedreamv45",
                "--image-resolution",
                "4:5",
            )
            dispatch = json.loads((run_dir / "dispatch.json").read_text(encoding="utf-8"))
            command = dispatch["commands"][0]["command"]
            self.assertIn(str(IMAGE_CLIENT), command)
            self.assertIn("--source", command)

            output = run_dir / "outputs/hero.png"
            output.write_bytes(b"test output")
            task_record = run_dir / "task_records/task_test_123.json"
            task_record.write_text(json.dumps({
                "format": "tensorslab.task@1",
                "kind": "image",
                "task_id": "task_test_123",
                "generation_status": "completed",
                "download_status": "completed",
                "outputs": [str(output)],
            }), encoding="utf-8")
            run_cli(
                WORKSHOP / "record_result.py",
                "--run",
                run_dir,
                "--task",
                "主图",
                "--task-record",
                task_record,
                "--qa", "product_truth=pass",
                "--qa",
                "visual_quality=pass",
                "--qa",
                "text_and_rights=not_applicable",
                "--qa",
                "publication_review=pass",
            )
            updated = json.loads(plan_path.read_text(encoding="utf-8"))
            self.assertEqual(updated["status"], "completed")
            self.assertEqual(updated["tasks"][0]["delivery_status"], "ready")

    def test_video_shots_can_be_revised_and_prepared_for_external_assembly(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            source = temp / "product.jpg"
            source.write_bytes(b"test fixture")
            output_root = temp / "runs"
            run_cli(
                WORKSHOP / "create_run.py",
                "--project",
                "travel-reel",
                "--scenario",
                "tourism-narrative-video",
                "--source",
                source,
                "--output-dir",
                output_root,
            )
            run_dir = output_root / "travel-reel"
            plan_path = run_dir / "plan.json"
            plan = json.loads(plan_path.read_text(encoding="utf-8"))
            self.assertEqual(plan["video_story"]["format"], "miaodashi.video-story@1")
            self.assertEqual(plan["tasks"][0]["shot"]["id"], "S01")
            plan["constraints"]["immutable_facts"] = ["rights-cleared destination image"]
            plan["constraints"]["brand_anchors"] = ["natural sunrise"]
            for task in plan["tasks"]:
                task["prompt"] = f"Create the approved visual for {task['name']}."
                task["shot"]["script_line"] = "Approved narration meaning."
            plan_path.write_text(json.dumps(plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            run_cli(WORKSHOP / "approve_run.py", "--run", run_dir, "--approved-by", "test-user")
            run_cli(WORKSHOP / "prepare_dispatch.py", "--run", run_dir)
            dispatch = json.loads((run_dir / "dispatch.json").read_text(encoding="utf-8"))
            self.assertIn("seedancev2", dispatch["commands"][0]["command"])
            for index, task in enumerate(plan["tasks"], start=1):
                output = run_dir / "outputs" / f"shot-{index}.mp4"
                output.write_bytes(b"test video")
                run_cli(
                    WORKSHOP / "record_result.py",
                    "--run",
                    run_dir,
                    "--task",
                    task["name"],
                    "--status",
                    "completed",
                    "--output",
                    output,
                    "--qa",
                    "product_truth=pass",
                    "--qa",
                    "visual_quality=pass",
                    "--qa",
                    "text_and_rights=not_applicable",
                    "--qa",
                    "publication_review=pass",
                )
            run_cli(WORKSHOP / "prepare_assembly.py", "--run", run_dir)
            assembly = json.loads((run_dir / "assemble_plan.json").read_text(encoding="utf-8"))
            self.assertEqual(assembly["mode"], "review_only_no_ffmpeg_execution")
            self.assertEqual(len(assembly["clips"]), 3)
            first_task = plan["tasks"][0]["name"]
            run_cli(
                WORKSHOP / "revise_shot.py",
                "--run",
                run_dir,
                "--task",
                first_task,
                "--reason",
                "need a closer opening",
                expected=2,
            )
            run_cli(
                WORKSHOP / "revise_shot.py",
                "--run",
                run_dir,
                "--task",
                first_task,
                "--reason",
                "need a closer opening",
                "--replace-approved",
            )
            revised = json.loads(plan_path.read_text(encoding="utf-8"))
            self.assertEqual(revised["tasks"][0]["status"], "needs_approval")
            self.assertNotIn(first_task, revised["execution"]["approval"]["task_digests"])
            self.assertEqual(len(revised["tasks"][0]["previous_outputs"]), 1)
            run_cli(
                WORKSHOP / "prepare_dispatch.py",
                "--run", run_dir,
                "--task", first_task,
                expected=2,
            )
            run_cli(
                WORKSHOP / "approve_run.py",
                "--run", run_dir,
                "--approved-by", "test-user",
                "--task", first_task,
            )
            run_cli(WORKSHOP / "prepare_dispatch.py", "--run", run_dir, "--task", first_task)

    def test_approval_rejects_changed_prompt_and_source_content(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            source = temp / "product.jpg"
            source.write_bytes(b"original fixture")
            output_root = temp / "runs"
            run_cli(
                WORKSHOP / "create_run.py",
                "--project", "approval-integrity",
                "--scenario", "listing-kit",
                "--source", source,
                "--output-count", 1,
                "--output-dir", output_root,
            )
            run_dir = output_root / "approval-integrity"
            plan_path = run_dir / "plan.json"
            plan = json.loads(plan_path.read_text(encoding="utf-8"))
            plan["constraints"]["immutable_facts"] = ["blue bottle"]
            plan["constraints"]["brand_anchors"] = ["white background"]
            plan["tasks"][0]["prompt"] = "Keep the approved blue bottle unchanged."
            plan_path.write_text(json.dumps(plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            run_cli(WORKSHOP / "approve_run.py", "--run", run_dir, "--approved-by", "reviewer")
            run_cli(WORKSHOP / "prepare_dispatch.py", "--run", run_dir)

            plan = json.loads(plan_path.read_text(encoding="utf-8"))
            plan["tasks"][0]["prompt"] = "Change the bottle to red."
            plan_path.write_text(json.dumps(plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            changed_prompt = run_cli(WORKSHOP / "prepare_dispatch.py", "--run", run_dir, expected=2)
            self.assertIn("approve it again", changed_prompt.stderr)

            plan["tasks"][0]["prompt"] = "Keep the approved blue bottle unchanged."
            plan_path.write_text(json.dumps(plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            source.write_bytes(b"changed fixture")
            changed_asset = run_cli(WORKSHOP / "prepare_dispatch.py", "--run", run_dir, expected=2)
            self.assertIn("source assets changed", changed_asset.stderr)

    def test_completed_generation_stays_blocked_until_required_qa_passes(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            source = temp / "product.jpg"
            source.write_bytes(b"test fixture")
            output_root = temp / "runs"
            run_cli(
                WORKSHOP / "create_run.py",
                "--project", "qa-gate",
                "--scenario", "listing-kit",
                "--source", source,
                "--output-count", 1,
                "--output-dir", output_root,
            )
            run_dir = output_root / "qa-gate"
            plan_path = run_dir / "plan.json"
            plan = json.loads(plan_path.read_text(encoding="utf-8"))
            plan["constraints"]["immutable_facts"] = ["black package"]
            plan["constraints"]["brand_anchors"] = ["soft light"]
            plan["tasks"][0]["prompt"] = "Keep the black package accurate."
            plan_path.write_text(json.dumps(plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            run_cli(WORKSHOP / "approve_run.py", "--run", run_dir, "--approved-by", "reviewer")
            output = run_dir / "outputs/result.png"
            output.write_bytes(b"result")
            run_cli(
                WORKSHOP / "record_result.py",
                "--run", run_dir,
                "--task", "主图",
                "--status", "completed",
                "--output", output,
                "--qa", "visual_quality=pass",
            )
            pending = json.loads(plan_path.read_text(encoding="utf-8"))
            self.assertEqual(pending["status"], "review_pending")
            self.assertEqual(pending["tasks"][0]["status"], "qa_pending")
            self.assertEqual(pending["tasks"][0]["delivery_status"], "blocked")


if __name__ == "__main__":
    unittest.main()
