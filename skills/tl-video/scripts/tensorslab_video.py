#!/usr/bin/env python3
"""
TensorsLab Video Generation API Client

Supports text-to-video and image-to-video generation using TensorsLab's models.
"""

import os
import sys
import time
import argparse
import json
import logging
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import urlparse
from typing import Callable, Optional, List

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from tensorslab_task_state import (  # noqa: E402
    DEFAULT_STATE_DIR,
    load_task_record,
    new_task_record,
    operation_result,
    save_task_record,
)

try:
    import requests
except ImportError:
    logging.getLogger(__name__).error(
        "Error: requests module is required. Install with: pip install requests"
    )
    sys.exit(1)


class TensorsLabAPIError(Exception):
    """TensorsLab API error with context."""
    pass


class TensorsLabSubmissionUnknown(TensorsLabAPIError):
    """The request may have reached the server, but no task ID was received."""


logger = logging.getLogger(__name__)

# API Configuration
BASE_URL = "https://api.tensorslab.com"
CONSOLE_URL = "https://tensorai.tensorslab.com/"
DEFAULT_OUTPUT_DIR = Path(".") / "tensorslab_output"

# Task status codes
TASK_STATUS = {
    1: "Pending",
    2: "Processing",
    3: "Completed",
    4: "Failed",
    5: "Uploading",
}

# Model → endpoint mapping
MODEL_ENDPOINTS = {
    "seedancev1": f"{BASE_URL}/v1/video/seedancev1",
    "seedancev15pro": f"{BASE_URL}/v1/video/seedancev15pro",
    "seedancev1profast": f"{BASE_URL}/v1/video/seedancev1profast",
    "seedancev2": f"{BASE_URL}/v1/video/seedancev2",
}

# Model → max duration
MODEL_MAX_DURATION = {
    "seedancev1": 10,
    "seedancev15pro": 10,
    "seedancev1profast": 10,
    "seedancev2": 15,
}

# Polling back-off settings
POLL_INITIAL_INTERVAL = 10
POLL_MAX_INTERVAL = 30
POLL_BACKOFF_FACTOR = 1.3
HEARTBEAT_INTERVAL = 60


def validate_inputs(
    *,
    prompt: str,
    model: str,
    ratio: str,
    duration: int,
    resolution: str,
    source_images: Optional[List[str]],
    image_url: Optional[str],
    generate_audio: bool,
    return_last_frame: bool,
    timeout: int = 1800,
) -> None:
    """Reject unsupported model and parameter combinations before billing."""
    if not prompt.strip():
        raise TensorsLabAPIError("Prompt must not be empty")
    if model not in MODEL_ENDPOINTS:
        raise TensorsLabAPIError(f"Unsupported video model: {model}")
    if not ratio.strip():
        raise TensorsLabAPIError("Ratio must not be empty")
    max_duration = MODEL_MAX_DURATION[model]
    if duration < 5 or duration > max_duration:
        raise TensorsLabAPIError(
            f"Duration must be between 5 and {max_duration} seconds for {model}"
        )
    if resolution == "1440p" and model != "seedancev2":
        raise TensorsLabAPIError("1440p is documented only for seedancev2")
    if (generate_audio or return_last_frame) and model != "seedancev2":
        raise TensorsLabAPIError("Audio and last-frame output are available only on seedancev2")
    if source_images and image_url:
        raise TensorsLabAPIError("Use local --source files or --image-url, not both")
    if source_images and len(source_images) > 2:
        raise TensorsLabAPIError("A video task accepts at most two source images")
    for value in source_images or []:
        if not Path(value).expanduser().is_file():
            raise TensorsLabAPIError(f"Source image does not exist: {value}")
    if image_url:
        parsed = urlparse(image_url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise TensorsLabAPIError("--image-url must be an http or https URL")
    if timeout < 1:
        raise TensorsLabAPIError("Timeout must be at least 1 second")


def request_preview(
    *,
    prompt: str,
    model: str,
    ratio: str,
    duration: int,
    resolution: str,
    fps: str,
    source_images: Optional[List[str]],
    image_url: Optional[str],
    generate_audio: bool,
    return_last_frame: bool,
    seed: Optional[int],
) -> dict:
    """Return a credential-free preview for documentation and preflight checks."""
    return {
        "method": "POST",
        "endpoint": MODEL_ENDPOINTS[model],
        "model": model,
        "prompt": prompt,
        "ratio": ratio,
        "duration": duration,
        "resolution": resolution,
        "fps": fps,
        "source_images": list(source_images or []),
        "image_url": image_url,
        "generate_audio": generate_audio,
        "return_last_frame": return_last_frame,
        "seed": seed,
        "submits_request": False,
    }


def _create_session() -> requests.Session:
    """Create a requests session with proxy disabled."""
    session = requests.Session()
    session.proxies = {"http": "", "https": ""}
    return session


_SESSION = _create_session()


def get_api_key() -> str:
    """Get API key from environment variable."""
    api_key = os.environ.get("TENSORSLAB_API_KEY")
    if not api_key:
        raise TensorsLabAPIError(
            "TENSORSLAB_API_KEY environment variable is not set.\n"
            "To get your API key:\n"
            f"1. Visit {CONSOLE_URL} and subscribe\n"
            "2. Get your API Key from the console\n"
            "3. Set the environment variable:\n"
            '   - Windows (PowerShell): $env:TENSORSLAB_API_KEY="your-key-here"\n'
            '   - Mac/Linux: export TENSORSLAB_API_KEY="your-key-here"'
        )
    return api_key


def ensure_output_dir(output_dir: Path):
    """Create output directory if it doesn't exist."""
    output_dir.mkdir(parents=True, exist_ok=True)


@contextmanager
def open_source_images(paths: Optional[List[str]]):
    """Safely open source image files, ensuring they are closed on exit."""
    handles = []
    try:
        for path in paths or []:
            expanded = Path(path).expanduser()
            f = expanded.open("rb")
            handles.append((expanded.name, f))
        yield handles
    finally:
        for _, f in handles:
            f.close()


def download_video(url: str, output_path: Path) -> bool:
    """Download a video from URL to local path with streaming."""
    try:
        response = _SESSION.get(url, timeout=300, stream=True)
        response.raise_for_status()
        total_size = int(response.headers.get("content-length", 0))

        with open(output_path, "wb") as f:
            if total_size > 0:
                downloaded = 0
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        percent = (downloaded / total_size) * 100
                        logger.info(f"\r📥 Downloading: {percent:.1f}%")
            else:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)

        logger.info(f"✅ Download complete: {output_path}")
        return True
    except Exception as e:
        logger.warning(f"⚠️ Failed to download video from {url}: {e}")
        return False


def generate_video(
    prompt: str,
    model: str = "seedancev1profast",
    ratio: str = "9:16",
    duration: int = 5,
    resolution: str = "720p",
    fps: str = "24",
    source_images: Optional[List[str]] = None,
    image_url: Optional[str] = None,
    generate_audio: bool = False,
    return_last_frame: bool = False,
    seed: Optional[int] = None,
    api_key: Optional[str] = None,
) -> str:
    """
    Generate a video using TensorsLab API.

    Returns:
        Task ID for tracking generation status.
    """
    validate_inputs(
        prompt=prompt,
        model=model,
        ratio=ratio,
        duration=duration,
        resolution=resolution,
        source_images=source_images,
        image_url=image_url,
        generate_audio=generate_audio,
        return_last_frame=return_last_frame,
    )
    if api_key is None:
        api_key = get_api_key()

    headers = {"Authorization": f"Bearer {api_key}"}

    files: list = [
        ("prompt", (None, prompt)),
        ("ratio", (None, ratio)),
        ("duration", (None, str(duration))),
        ("resolution", (None, resolution)),
        ("fps", (None, fps)),
    ]

    if seed is not None:
        files.append(("seed", (None, str(seed))))
    if generate_audio and model == "seedancev2":
        files.append(("generate_audio", (None, "1")))
    if return_last_frame and model == "seedancev2":
        files.append(("return_last_frame", (None, "1")))

    endpoint = MODEL_ENDPOINTS.get(model, MODEL_ENDPOINTS["seedancev2"])

    with open_source_images(source_images) as img_handles:
        for name, fh in img_handles:
            files.append(("sourceImage", (name, fh)))
        if not img_handles and image_url:
            files.append(("imageUrl", (None, image_url)))

        try:
            logger.info(f"🎬 Generating video using {model}...")
            logger.info(f"📝 Prompt: {prompt[:100]}{'...' if len(prompt) > 100 else ''}")
            logger.info(f"⚙️ Settings: {ratio} @ {resolution}, {duration}s, {fps}fps")

            response = _SESSION.post(endpoint, headers=headers, files=files, timeout=60)
        except requests.exceptions.RequestException as e:
            raise TensorsLabSubmissionUnknown(f"Submission outcome is unknown after network error: {e}") from e

    logger.debug(f"API Response ({response.status_code}): {response.text}")

    try:
        result = response.json()
    except ValueError:
        raise TensorsLabSubmissionUnknown(
            f"Invalid JSON response (HTTP {response.status_code}): {response.text}"
        )

    if result.get("code") == 1000:
        task_id = result.get("data", {}).get("taskid")
        if not task_id:
            raise TensorsLabSubmissionUnknown("API reported success but returned no task ID")
        logger.info(f"✅ Task created successfully! Task ID: {task_id}")
        return task_id

    error_code = result.get("code")
    error_msg = result.get("msg", "Unknown error")
    if error_code == 9000:
        raise TensorsLabAPIError(
            f"Insufficient credits. Please top up at {CONSOLE_URL}"
        )
    raise TensorsLabAPIError(f"{error_msg} (Code: {error_code})")


def query_task_status(
    task_id: str, api_key: Optional[str] = None, more_info: bool = False
) -> Optional[dict]:
    """Query the status of a video generation task."""
    if api_key is None:
        api_key = get_api_key()

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    try:
        response = _SESSION.post(
            f"{BASE_URL}/v1/video/infobytaskid",
            headers=headers,
            json={"taskid": task_id, "moreTaskInfo": more_info},
            timeout=30,
        )
        result = response.json()
        if result.get("code") == 1000:
            return result.get("data", {})
        logger.error(f"❌ Error querying task: {result.get('msg', 'Unknown error')}")
    except (ValueError, requests.exceptions.RequestException) as e:
        logger.error(f"❌ Error querying task status: {e}")
    return None


def generation_status(task_data: dict) -> str:
    return {
        1: "queued",
        2: "processing",
        3: "completed",
        4: "failed",
        5: "uploading",
    }.get(task_data.get("task_status"), "unknown")


def update_record_from_status(record: dict, task_data: dict) -> None:
    status = generation_status(task_data)
    record["generation_status"] = status
    record["server_status"] = task_data.get("task_status")
    record["result_urls"] = list(task_data.get("url", []) or [])
    record["error"] = None
    record["next_action"] = {
        "queued": "wait",
        "processing": "wait",
        "uploading": "wait",
        "completed": "download",
        "failed": None,
        "unknown": "status",
    }[status]
    if status == "failed":
        record["error"] = {
            "code": "GENERATION_FAILED",
            "message": task_data.get("message", "Unknown error"),
        }


def wait_for_completion(
    task_id: str,
    api_key: Optional[str] = None,
    timeout: int = 1800,
    on_status: Optional[Callable[[dict], None]] = None,
) -> dict:
    """Wait for a terminal server state without downloading or resubmitting."""
    if api_key is None:
        api_key = get_api_key()
    start_time = time.time()
    interval = POLL_INITIAL_INTERVAL
    last_heartbeat = 0
    logger.info("⏳ Waiting for video generation to complete...")
    while time.time() - start_time < timeout:
        task_data = query_task_status(task_id, api_key)
        if not task_data:
            time.sleep(interval)
            interval = min(interval * POLL_BACKOFF_FACTOR, POLL_MAX_INTERVAL)
            continue
        if on_status is not None:
            on_status(task_data)
        status = task_data.get("task_status")
        elapsed = int(time.time() - start_time)
        if status == 2 and elapsed - last_heartbeat >= HEARTBEAT_INTERVAL:
            logger.info(f"🚀 正在渲染电影级大片，已耗时 {elapsed} 秒，请稍安勿躁...")
            last_heartbeat = elapsed
        logger.info(f"🔄 Status: {TASK_STATUS.get(status, 'Unknown')} (elapsed: {elapsed}s)")
        if status == 3:
            return task_data
        if status == 4:
            raise TensorsLabAPIError(f"Task failed: {task_data.get('message', 'Unknown error')}")
        time.sleep(interval)
        interval = min(interval * POLL_BACKOFF_FACTOR, POLL_MAX_INTERVAL)
    raise TensorsLabAPIError(f"Timeout waiting for task completion (waited {timeout}s)")


def download_task_outputs(task_id: str, task_data: dict, output_dir: Path) -> List[str]:
    """Download a completed task's current result URLs without creating a task."""
    if generation_status(task_data) != "completed":
        raise TensorsLabAPIError("Task is not completed; use status or wait before download")
    ensure_output_dir(output_dir)
    urls = list(task_data.get("url", []) or [])
    downloaded_files: List[str] = []
    for i, url in enumerate(urls):
        ext = Path(urlparse(url).path).suffix
        if not ext or len(ext) > 5:
            ext = ".mp4"
        output_path = output_dir / f"{task_id}_{i}{ext}"
        logger.info(f"📥 Downloading video {i + 1}/{len(urls)}: {output_path}")
        if download_video(url, output_path):
            downloaded_files.append(str(output_path))
    return downloaded_files


def update_record_from_download(record: dict, downloaded: List[str]) -> None:
    record["outputs"] = [str(Path(path).expanduser().resolve()) for path in downloaded]
    expected = len(record.get("result_urls", []))
    if expected == 0:
        record["download_status"] = "failed"
        record["error"] = {"code": "NO_OUTPUTS", "message": "Completed task returned no output URLs"}
    elif len(downloaded) == expected:
        record["download_status"] = "completed"
        record["error"] = None
    elif downloaded:
        record["download_status"] = "partial"
        record["error"] = {"code": "DOWNLOAD_INCOMPLETE", "message": "One or more outputs could not be downloaded"}
    else:
        record["download_status"] = "failed"
        record["error"] = {"code": "DOWNLOAD_FAILED", "message": "No outputs could be downloaded"}
    record["next_action"] = None if record["download_status"] == "completed" else "download"


def wait_and_download(
    task_id: str,
    api_key: Optional[str] = None,
    timeout: int = 1800,
    output_dir: Optional[Path] = None,
) -> List[str]:
    """Wait for task completion with exponential back-off, then download results."""
    if api_key is None:
        api_key = get_api_key()
    if output_dir is None:
        output_dir = DEFAULT_OUTPUT_DIR

    task_data = wait_for_completion(task_id, api_key=api_key, timeout=timeout)
    return download_task_outputs(task_id, task_data, output_dir)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate videos using TensorsLab API",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python tensorslab_video.py "a spaceship flying through space"
  python tensorslab_video.py "sunset over ocean waves" --duration 10 --ratio 16:9
  python tensorslab_video.py "make this photo come alive" --source portrait.jpg
  python tensorslab_video.py "abstract flowing colors" --model seedancev1profast
  python tensorslab_video.py "epic mountain timelapse" --resolution 1440p --duration 10 --audio
        """,
    )

    parser.add_argument("prompt", nargs="?", help="Text prompt for video generation")
    parser.add_argument(
        "--operation",
        choices=["run", "submit", "status", "wait", "download"],
        default="run",
        help="run submits, waits, and downloads; other operations are independently resumable",
    )
    parser.add_argument("--task-id", help="Existing task ID for status, wait, or download")
    parser.add_argument(
        "--state-dir",
        default=str(DEFAULT_STATE_DIR),
        help="Directory for durable task records (default: ./.tensorslab_tasks)",
    )
    parser.add_argument(
        "--model", "-m",
        choices=list(MODEL_ENDPOINTS.keys()),
        default="seedancev1profast",
        help="Model to use (default: seedancev1profast)",
    )
    parser.add_argument(
        "--ratio", "-r", default="9:16", help="Video aspect ratio (default: 9:16)"
    )
    parser.add_argument(
        "--duration", "-d", type=int, default=5,
        help="Video duration in seconds (5-15, default: 5)",
    )
    parser.add_argument(
        "--resolution",
        choices=["480p", "720p", "1080p", "1440p"],
        default="720p",
        help="Video resolution (default: 720p)",
    )
    parser.add_argument("--fps", "-f", default="24", help="Frame rate (default: 24)")
    parser.add_argument(
        "--source", "-s", action="append", dest="sources",
        help="Source image path for image-to-video (max 2 images)",
    )
    parser.add_argument("--image-url", help="Source image URL for image-to-video")
    parser.add_argument(
        "--audio", action="store_true",
        help="Generate audio with video (seedancev2 only)",
    )
    parser.add_argument(
        "--last-frame", action="store_true",
        help="Return the last frame as image (seedancev2 only)",
    )
    parser.add_argument("--seed", type=int, help="Random seed for reproducibility")
    parser.add_argument("--api-key", help="TensorsLab API key (overrides env var)")
    parser.add_argument(
        "--timeout", type=int, default=1800,
        help="Maximum wait time in seconds (default: 1800 = 30 minutes)",
    )
    parser.add_argument(
        "--output-dir", "-o", type=str, default=None,
        help="Output directory path (default: ./tensorslab_output)",
    )
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    parser.add_argument("--json", action="store_true", help="Print a structured JSON result for the run operation")
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Validate inputs and print the request plan without using an API key",
    )

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.debug else logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
    )

    output_dir = Path(args.output_dir) if args.output_dir else DEFAULT_OUTPUT_DIR
    state_dir = Path(args.state_dir)

    try:
        if args.operation in {"run", "submit"}:
            if not args.prompt:
                raise TensorsLabAPIError("A prompt is required for run or submit")
            validate_inputs(
                prompt=args.prompt,
                model=args.model,
                ratio=args.ratio,
                duration=args.duration,
                resolution=args.resolution,
                source_images=args.sources,
                image_url=args.image_url,
                generate_audio=args.audio,
                return_last_frame=args.last_frame,
                timeout=args.timeout,
            )
            preview = request_preview(
                prompt=args.prompt,
                model=args.model,
                ratio=args.ratio,
                duration=args.duration,
                resolution=args.resolution,
                fps=args.fps,
                source_images=args.sources,
                image_url=args.image_url,
                generate_audio=args.audio,
                return_last_frame=args.last_frame,
                seed=args.seed,
            )
            if args.dry_run:
                print(json.dumps(preview, ensure_ascii=False, indent=2))
                return 0
            request_record = dict(preview)
            request_record["submits_request"] = True
            try:
                task_id = generate_video(
                    prompt=args.prompt,
                    model=args.model,
                    ratio=args.ratio,
                    duration=args.duration,
                    resolution=args.resolution,
                    fps=args.fps,
                    source_images=args.sources,
                    image_url=args.image_url,
                    generate_audio=args.audio,
                    return_last_frame=args.last_frame,
                    seed=args.seed,
                    api_key=args.api_key,
                )
            except TensorsLabSubmissionUnknown as error:
                record = new_task_record(
                    kind="video",
                    task_id=None,
                    request=request_record,
                    output_dir=output_dir,
                    submission_status="unknown",
                )
                record["error"] = {"code": "SUBMISSION_UNKNOWN", "message": str(error)}
                record["next_action"] = "Check the provider dashboard; do not automatically resubmit."
                path = save_task_record(state_dir, record)
                print(json.dumps(operation_result(record, args.operation, path), ensure_ascii=False, indent=2))
                return 1
            except TensorsLabAPIError as error:
                logger.error(f"❌ {error}")
                record = new_task_record(
                    kind="video",
                    task_id=None,
                    request=request_record,
                    output_dir=output_dir,
                    submission_status="rejected",
                )
                record["generation_status"] = "failed"
                record["error"] = {"code": "SUBMISSION_REJECTED", "message": str(error)}
                record["next_action"] = None
                path = save_task_record(state_dir, record)
                if args.operation == "submit" or args.json:
                    print(json.dumps(operation_result(record, args.operation, path), ensure_ascii=False, indent=2))
                return 1
            record = new_task_record(
                kind="video",
                task_id=task_id,
                request=request_record,
                output_dir=output_dir,
            )
            record["next_action"] = "wait"
            path = save_task_record(state_dir, record)
            if args.operation == "submit":
                print(json.dumps(operation_result(record, "submit", path), ensure_ascii=False, indent=2))
                return 0

            def persist_status(task_data: dict) -> None:
                update_record_from_status(record, task_data)
                save_task_record(state_dir, record)

            try:
                task_data = wait_for_completion(
                    task_id,
                    api_key=args.api_key,
                    timeout=args.timeout,
                    on_status=persist_status,
                )
            except TensorsLabAPIError as error:
                if record.get("generation_status") != "failed":
                    record["error"] = {"code": "WAIT_TIMEOUT", "message": str(error)}
                    record["next_action"] = "wait"
                path = save_task_record(state_dir, record)
                if args.json:
                    print(json.dumps(operation_result(record, "run", path), ensure_ascii=False, indent=2))
                raise
            downloaded = download_task_outputs(task_id, task_data, output_dir)
            update_record_from_download(record, downloaded)
            path = save_task_record(state_dir, record)
            if args.json:
                print(json.dumps(operation_result(record, "run", path), ensure_ascii=False, indent=2))
            logger.info(f"\n🎉 您的视频处理完毕！已存放于 {output_dir}/")
            return 0

        if args.dry_run:
            raise TensorsLabAPIError("--dry-run is available only for run or submit")
        if not args.task_id:
            raise TensorsLabAPIError("--task-id is required for status, wait, or download")
        record = load_task_record(state_dir, args.task_id)
        if record is not None:
            if record.get("kind") != "video" or record.get("task_id") != args.task_id:
                raise TensorsLabAPIError("Stored task record does not match this video task")
        else:
            record = new_task_record(
                kind="video",
                task_id=args.task_id,
                request={"source": "existing_task_id"},
                output_dir=output_dir,
                submission_status="external",
            )
        if args.output_dir is None and record.get("output_dir"):
            output_dir = Path(record["output_dir"])

        if args.operation == "status":
            task_data = query_task_status(args.task_id, args.api_key)
            if not task_data:
                record["error"] = {"code": "QUERY_FAILED", "message": "Task status could not be read"}
                record["next_action"] = "status"
                path = save_task_record(state_dir, record)
                print(json.dumps(operation_result(record, "status", path), ensure_ascii=False, indent=2))
                return 1
            update_record_from_status(record, task_data)
            path = save_task_record(state_dir, record)
            print(json.dumps(operation_result(record, "status", path), ensure_ascii=False, indent=2))
            return 1 if record["generation_status"] == "failed" else 0

        if args.operation == "wait":
            def persist_wait_status(task_data: dict) -> None:
                update_record_from_status(record, task_data)
                save_task_record(state_dir, record)

            try:
                task_data = wait_for_completion(
                    args.task_id,
                    api_key=args.api_key,
                    timeout=args.timeout,
                    on_status=persist_wait_status,
                )
                update_record_from_status(record, task_data)
                path = save_task_record(state_dir, record)
                print(json.dumps(operation_result(record, "wait", path), ensure_ascii=False, indent=2))
                return 0
            except TensorsLabAPIError as error:
                if record.get("generation_status") != "failed":
                    record["error"] = {"code": "WAIT_TIMEOUT", "message": str(error)}
                    record["next_action"] = "wait"
                path = save_task_record(state_dir, record)
                print(json.dumps(operation_result(record, "wait", path), ensure_ascii=False, indent=2))
                return 1

        task_data = query_task_status(args.task_id, args.api_key)
        if not task_data:
            record["error"] = {"code": "QUERY_FAILED", "message": "Task status could not be read"}
            record["next_action"] = "download"
            path = save_task_record(state_dir, record)
            print(json.dumps(operation_result(record, "download", path), ensure_ascii=False, indent=2))
            return 1
        update_record_from_status(record, task_data)
        if record["generation_status"] != "completed":
            record["error"] = {"code": "NOT_COMPLETED", "message": "Task is not completed"}
            path = save_task_record(state_dir, record)
            print(json.dumps(operation_result(record, "download", path), ensure_ascii=False, indent=2))
            return 1
        downloaded = download_task_outputs(args.task_id, task_data, output_dir)
        update_record_from_download(record, downloaded)
        path = save_task_record(state_dir, record)
        print(json.dumps(operation_result(record, "download", path), ensure_ascii=False, indent=2))
        return 0 if record["download_status"] == "completed" else 1
    except TensorsLabAPIError as e:
        logger.error(f"❌ {e}")
        return 1
    except (OSError, ValueError) as e:
        logger.error(f"❌ Task record error: {e}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
