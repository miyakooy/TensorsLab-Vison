from __future__ import annotations

import json
import importlib.util
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


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

            run_cli(WORKSHOP / "approve_run.py", "--run", run_dir, "--approved-by", "test-user")
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
            run_cli(
                WORKSHOP / "record_result.py",
                "--run",
                run_dir,
                "--task",
                "主图",
                "--status",
                "completed",
                "--output",
                output,
                "--qa",
                "product_truth=pass",
            )
            updated = json.loads(plan_path.read_text(encoding="utf-8"))
            self.assertEqual(updated["status"], "completed")


if __name__ == "__main__":
    unittest.main()
