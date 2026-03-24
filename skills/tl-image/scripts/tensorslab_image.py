#!/usr/bin/env python3
"""
TensorsLab Image Generation API Client

Supports text-to-image and image-to-image generation using TensorsLab's models.
"""

import os
import sys
import time
import argparse
import logging
import mimetypes
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

# Image status codes
IMAGE_STATUS = {
    1: "Queued",
    2: "Processing",
    3: "Completed",
    4: "Failed",
}

# Model → endpoint mapping
MODEL_ENDPOINTS = {
    "seedreamv4": f"{BASE_URL}/v1/images/seedreamv4",
    "seedreamv45": f"{BASE_URL}/v1/images/seedreamv45",
    "zimage": f"{BASE_URL}/v1/images/zimage",
}

# Initial and max back-off intervals for polling (seconds)
POLL_INITIAL_INTERVAL = 3
POLL_MAX_INTERVAL = 15
POLL_BACKOFF_FACTOR = 1.5


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


def download_image(url: str, output_path: Path) -> Optional[Path]:
    """Download an image from URL to local path."""
    try:
        response = _SESSION.get(url, timeout=30)
        response.raise_for_status()

        content_type = response.headers.get("content-type", "").split(";")[0].strip()
        ext = mimetypes.guess_extension(content_type)
        if ext == ".jpe":
            ext = ".jpg"
        if not ext:
            ext = Path(urlparse(url).path).suffix
        if not ext or len(ext) > 6:
            ext = ".png"

        final_path = output_path.with_suffix(ext)
        final_path.write_bytes(response.content)
        return final_path
    except Exception as e:
        logger.warning(f"Warning: Failed to download image from {url}: {e}")
        return None


def generate_image(
    prompt: str,
    model: str = "seedreamv4",
    resolution: str = "2K",
    source_images: Optional[List[str]] = None,
    image_url: Optional[str] = None,
    api_key: Optional[str] = None,
) -> str:
    """
    Generate an image using TensorsLab API.

    Returns:
        Task ID for tracking generation status.
    """
    if api_key is None:
        api_key = get_api_key()

    headers = {"Authorization": f"Bearer {api_key}"}

    files: list = [
        ("prompt", (None, prompt)),
        ("resolution", (None, resolution)),
    ]

    if model in ("seedreamv4", "seedreamv45"):
        files.append(("category", (None, model)))
    elif model == "zimage":
        files.append(("prompt_extend", (None, "1")))

    endpoint = MODEL_ENDPOINTS.get(model, MODEL_ENDPOINTS["seedreamv45"])

    with open_source_images(source_images) as img_handles:
        for name, fh in img_handles:
            files.append(("sourceImage", (name, fh)))
        if not img_handles and image_url:
            files.append(("imageUrl", (None, image_url)))

        try:
            logger.info(f"🎨 Generating image using {model}...")
            logger.info(f"📝 Prompt: {prompt[:100]}{'...' if len(prompt) > 100 else ''}")

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


def query_task_status(task_id: str, api_key: Optional[str] = None) -> Optional[dict]:
    """Query the status of an image generation task."""
    if api_key is None:
        api_key = get_api_key()

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    try:
        response = _SESSION.post(
            f"{BASE_URL}/v1/images/infobytaskid",
            headers=headers,
            json={"taskid": task_id},
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
    timeout: int = 300,
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

    logger.info("⏳ Waiting for image generation to complete...")

    while time.time() - start_time < timeout:
        task_data = query_task_status(task_id, api_key)
        if not task_data:
            time.sleep(interval)
            interval = min(interval * POLL_BACKOFF_FACTOR, POLL_MAX_INTERVAL)
            continue

        status = task_data.get("image_status")
        elapsed = int(time.time() - start_time)
        logger.info(
            f"🔄 Status: {IMAGE_STATUS.get(status, 'Unknown')} (elapsed: {elapsed}s)"
        )

        if status == 3:  # Completed
            logger.info("✅ Task completed!")
            urls = task_data.get("url", [])
            if not urls:
                logger.warning("⚠️ No images returned")
                return downloaded_files

            for i, url in enumerate(urls):
                output_path = output_dir / f"{task_id}_{i}"
                logger.info(f"📥 Downloading image {i + 1}/{len(urls)}")
                final_path = download_image(url, output_path)
                if final_path:
                    downloaded_files.append(str(final_path))
            return downloaded_files

        if status == 4:  # Failed
            error_msg = task_data.get("error_message", "Unknown error")
            raise TensorsLabAPIError(f"Task failed: {error_msg}")

        time.sleep(interval)
        interval = min(interval * POLL_BACKOFF_FACTOR, POLL_MAX_INTERVAL)

    raise TensorsLabAPIError(f"Timeout waiting for task completion (waited {timeout}s)")


def main():
    parser = argparse.ArgumentParser(
        description="Generate images using TensorsLab API",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python tensorslab_image.py "a cat on the moon"
  python tensorslab_image.py "watercolor style" --source cat.png
  python tensorslab_image.py "sunset over mountains" --model seedreamv45 --resolution 16:9
        """,
    )

    parser.add_argument("prompt", help="Text prompt for image generation")
    parser.add_argument(
        "--model", "-m",
        choices=list(MODEL_ENDPOINTS.keys()),
        default="seedreamv4",
        help="Model to use (default: seedreamv4)",
    )
    parser.add_argument(
        "--resolution", "-r",
        default="2K",
        help="Resolution: aspect ratio (9:16, 16:9, 1:1, etc.), level (2K, 4K), or WxH",
    )
    parser.add_argument(
        "--source", "-s",
        action="append",
        dest="sources",
        help="Source image path for image-to-image (can be used multiple times)",
    )
    parser.add_argument("--image-url", help="Source image URL for image-to-image")
    parser.add_argument("--api-key", help="TensorsLab API key (overrides env var)")
    parser.add_argument(
        "--poll-interval",
        type=int,
        default=POLL_INITIAL_INTERVAL,
        help=f"Initial status check interval in seconds (default: {POLL_INITIAL_INTERVAL})",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=300,
        help="Maximum wait time in seconds (default: 300)",
    )
    parser.add_argument(
        "--output-dir", "-o",
        type=str,
        default=None,
        help="Output directory path (default: ./tensorslab_output)",
    )
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.debug else logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
    )

    output_dir = Path(args.output_dir) if args.output_dir else DEFAULT_OUTPUT_DIR

    try:
        task_id = generate_image(
            prompt=args.prompt,
            model=args.model,
            resolution=args.resolution,
            source_images=args.sources,
            image_url=args.image_url,
            api_key=args.api_key,
        )

        downloaded = wait_and_download(
            task_id=task_id,
            api_key=args.api_key,
            timeout=args.timeout,
            output_dir=output_dir,
        )

        logger.info(f"\n🎉 All done! Downloaded {len(downloaded)} image(s) to {output_dir}/")
        for f in downloaded:
            logger.info(f"   - {f}")
    except TensorsLabAPIError as e:
        logger.error(f"❌ {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
