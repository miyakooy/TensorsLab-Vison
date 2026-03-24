#!/usr/bin/env python3
"""
TensorsLab Video Generation API Client

Supports text-to-video and image-to-video generation using TensorsLab's models.
"""

import os
import sys
import time
import argparse
import logging
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import urlparse
from typing import Optional, List

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
            f = open(path, "rb")
            handles.append((os.path.basename(path), f))
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
            raise TensorsLabAPIError(f"Network error: {e}") from e

    logger.debug(f"API Response ({response.status_code}): {response.text}")

    try:
        result = response.json()
    except ValueError:
        raise TensorsLabAPIError(
            f"Invalid JSON response (HTTP {response.status_code}): {response.text}"
        )

    if result.get("code") == 1000:
        task_id = result.get("data", {}).get("taskid")
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

    ensure_output_dir(output_dir)
    downloaded_files: List[str] = []
    start_time = time.time()
    interval = POLL_INITIAL_INTERVAL
    last_heartbeat = 0

    logger.info("⏳ Waiting for video generation to complete...")
    logger.info("   (This may take several minutes - please be patient)")

    while time.time() - start_time < timeout:
        task_data = query_task_status(task_id, api_key)
        if not task_data:
            time.sleep(interval)
            interval = min(interval * POLL_BACKOFF_FACTOR, POLL_MAX_INTERVAL)
            continue

        status = task_data.get("task_status")
        elapsed = int(time.time() - start_time)

        # Heartbeat every 60 seconds during processing
        if status == 2 and elapsed - last_heartbeat >= HEARTBEAT_INTERVAL:
            logger.info(f"🚀 正在渲染电影级大片，已耗时 {elapsed} 秒，请稍安勿躁...")
            last_heartbeat = elapsed

        logger.info(
            f"🔄 Status: {TASK_STATUS.get(status, 'Unknown')} (elapsed: {elapsed}s)"
        )

        if status == 3:  # Completed
            logger.info("✅ Task completed!")
            urls = task_data.get("url", [])
            if not urls:
                logger.warning("⚠️ No videos returned")
                return downloaded_files

            for i, url in enumerate(urls):
                url_path = urlparse(url).path
                ext = Path(url_path).suffix
                if not ext or len(ext) > 5:
                    ext = ".mp4"
                filename = f"{task_id}_{i}{ext}"
                output_path = output_dir / filename

                logger.info(f"📥 Downloading video {i + 1}/{len(urls)}: {output_path}")
                if download_video(url, output_path):
                    downloaded_files.append(str(output_path))
            return downloaded_files

        if status == 4:  # Failed
            error_msg = task_data.get("message", "Unknown error")
            raise TensorsLabAPIError(f"Task failed: {error_msg}")

        time.sleep(interval)
        interval = min(interval * POLL_BACKOFF_FACTOR, POLL_MAX_INTERVAL)

    raise TensorsLabAPIError(f"Timeout waiting for task completion (waited {timeout}s)")


def main():
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

    parser.add_argument("prompt", help="Text prompt for video generation")
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

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.debug else logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
    )

    output_dir = Path(args.output_dir) if args.output_dir else DEFAULT_OUTPUT_DIR

    # Validate duration
    max_duration = MODEL_MAX_DURATION.get(args.model, 10)
    if args.duration < 5 or args.duration > max_duration:
        logger.error(
            f"❌ Error: duration must be between 5 and {max_duration} seconds for {args.model}"
        )
        sys.exit(1)

    # Validate source images count
    if args.sources and len(args.sources) > 2:
        logger.error("❌ Error: maximum 2 source images allowed")
        sys.exit(1)

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

        downloaded = wait_and_download(
            task_id=task_id,
            api_key=args.api_key,
            timeout=args.timeout,
            output_dir=output_dir,
        )

        logger.info(f"\n🎉 您的视频处理完毕！已存放于 {output_dir}/")
        for f in downloaded:
            logger.info(f"   - {f}")
    except TensorsLabAPIError as e:
        logger.error(f"❌ {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
