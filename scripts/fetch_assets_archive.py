import requests
import os
import time
import json
import config
import settings

PEXELS_API_KEY = settings.PEXELS_API_KEY
PEXELS_HEADERS = {"Authorization": PEXELS_API_KEY} if PEXELS_API_KEY else {}

# Pixabay — secondary video source with a completely different clip library.
# Free API key from https://pixabay.com/api/docs/
PIXABAY_API_KEY = settings.PIXABAY_API_KEY

# Generic fallback queries when niche-specific searches return nothing
FALLBACK_QUERIES = [
    "technology abstract",
    "code programming",
    "digital network",
    "data visualization",
    "circuit board",
]

# ── Clip Deduplication ──
# Tracks every Pexels clip ID used across all videos.
# Prevents the same stock footage from appearing in multiple videos,
# which YouTube's Content ID system can fingerprint and flag as mass-produced.
USED_CLIPS_FILE = config.USED_CLIPS_FILE


def _load_used_clips() -> set:
    """Load the set of previously used clip IDs (stored as strings)."""
    try:
        with open(USED_CLIPS_FILE, "r") as f:
            data = json.load(f)
            return set(str(cid) for cid in data.get("clip_ids", []))
    except (FileNotFoundError, json.JSONDecodeError):
        return set()


def _save_used_clip(clip_id) -> None:
    """Add a clip ID to the used clips log. All IDs stored as strings."""
    used = _load_used_clips()
    used.add(str(clip_id))
    with open(USED_CLIPS_FILE, "w") as f:
        json.dump({"clip_ids": sorted(list(used))}, f, indent=2)


def _search_pexels(query: str, per_page: int = 15) -> dict:
    """Execute a single Pexels video search. Returns API response dict."""
    url = "https://api.pexels.com/videos/search"
    params = {
        "query": query,
        "orientation": "portrait",  # 9:16 vertical only
        "size": "medium",
        "per_page": per_page,
        "page": 1
    }
    try:
        response = requests.get(url, headers=PEXELS_HEADERS, params=params, timeout=15)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        print(f"    ⚠ Pexels API error for '{query}': {e}")
        return {}


def _search_pixabay(query: str, per_page: int = 10) -> list:
    """
    Search Pixabay for vertical video clips.
    Returns list of (download_url, clip_id) tuples.
    """
    if not PIXABAY_API_KEY:
        return []

    url = "https://pixabay.com/api/videos/"
    params = {
        "key": PIXABAY_API_KEY,
        "q": query,
        "video_type": "film",
        "per_page": per_page,
        "safesearch": "true",
    }
    try:
        response = requests.get(url, params=params, timeout=15)
        response.raise_for_status()
        data = response.json()
    except requests.RequestException as e:
        print(f"    ⚠ Pixabay API error for '{query}': {e}")
        return []

    results = []
    for hit in data.get("hits", []):
        clip_id = hit.get("id", 0)
        # Prefer medium quality, fall back to small
        videos = hit.get("videos", {})
        for quality in ("medium", "small", "tiny"):
            vid = videos.get(quality, {})
            if vid.get("url") and vid.get("width", 0) >= 360:
                results.append((vid["url"], f"pixabay_{clip_id}"))
                break

    return results


def _pick_best_clip(data: dict, used_clips: set) -> tuple[str | None, int | None]:
    """
    From Pexels API response, pick the best video file URL.
    Skips clips that have already been used in previous videos.
    Priority: 1080x1920 portrait > any portrait > any clip.

    Returns (url, clip_id) or (None, None).
    """
    if not data.get("videos"):
        return None, None

    for video in data["videos"]:
        clip_id = str(video.get("id", 0))  # Normalize to string for dedup

        # Skip clips we've already used in other videos
        if clip_id in used_clips:
            continue

        # Skip clips shorter than 5 seconds — too short to be useful
        if video.get("duration", 0) < 5:
            continue

        # Pass 1: Look for exact 1080x1920
        for file in video["video_files"]:
            w, h = file.get("width", 0), file.get("height", 0)
            if w == 1080 and h >= 1920:
                return file["link"], clip_id

        # Pass 2: Any portrait clip (height > width)
        for file in video["video_files"]:
            w, h = file.get("width", 0), file.get("height", 0)
            if h > w and w >= 720:
                return file["link"], clip_id

        # Pass 3: Any reasonable resolution (FFmpeg will crop it)
        for file in video["video_files"]:
            w, h = file.get("width", 0), file.get("height", 0)
            if w >= 720 or h >= 720:
                return file["link"], clip_id

    return None, None


def _download_clip(url: str, output_path: str) -> bool:
    """Download a video file. Returns True if successful and file is valid."""
    try:
        response = requests.get(url, stream=True, timeout=30)
        response.raise_for_status()

        with open(output_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)

        # Validate: reject files smaller than 50KB (likely corrupt/empty)
        file_size = os.path.getsize(output_path)
        if file_size < 50 * 1024:
            print(f"    ⚠ Downloaded file too small ({file_size} bytes), skipping")
            os.remove(output_path)
            return False

        return True
    except requests.RequestException as e:
        print(f"    ⚠ Download failed: {e}")
        if os.path.exists(output_path):
            os.remove(output_path)
        return False


def fetch_video_for_scene(query: str, scene_number: int, output_dir: str) -> str | None:
    """
    Downloads one vertical video clip for a scene.
    Tries multiple search strategies before giving up:
      1. Full query (e.g. "quantum computing circuit")
      2. First word only (e.g. "quantum")
      3. Generic fallback queries (e.g. "technology abstract")

    Skips clips already used in previous videos (deduplication via used_clips.json).

    Returns local file path or None.
    """
    clip_path = os.path.join(output_dir, f"scene_{scene_number}.mp4")
    used_clips = _load_used_clips()

    # Strategy 1: Full query
    print(f"    Searching: '{query}'")
    data = _search_pexels(query)
    clip_url, clip_id = _pick_best_clip(data, used_clips)

    # Strategy 2: First word only
    if not clip_url and " " in query:
        first_word = query.split()[0]
        print(f"    Broadening search: '{first_word}'")
        data = _search_pexels(first_word)
        clip_url, clip_id = _pick_best_clip(data, used_clips)

    # Strategy 3: Generic Pexels fallbacks
    if not clip_url:
        for fallback in FALLBACK_QUERIES:
            print(f"    Trying fallback: '{fallback}'")
            data = _search_pexels(fallback)
            clip_url, clip_id = _pick_best_clip(data, used_clips)
            if clip_url:
                break

    # Strategy 4: Pixabay (completely different clip library)
    if not clip_url and PIXABAY_API_KEY:
        print(f"    Trying Pixabay: '{query}'")
        pixabay_results = _search_pixabay(query)
        for px_url, px_id in pixabay_results:
            if px_id not in used_clips:
                clip_url = px_url
                clip_id = px_id
                break

    if not clip_url:
        print(f"    ✗ No clip found for scene {scene_number}")
        return None

    # Download
    print(f"    Downloading clip for scene {scene_number}...")
    if _download_clip(clip_url, clip_path):
        # Log clip ID to prevent reuse in future videos
        if clip_id:
            _save_used_clip(clip_id)
        size_mb = os.path.getsize(clip_path) / (1024 * 1024)
        print(f"    ✓ Scene {scene_number}: {size_mb:.1f} MB (clip #{clip_id})")
        return clip_path

    return None


def fetch_all_assets(scenes: list, output_dir: str) -> list:
    """Downloads clips for all scenes. Returns list of paths (None for failures)."""
    os.makedirs(output_dir, exist_ok=True)
    paths = []

    for scene in scenes:
        path = fetch_video_for_scene(
            scene.get("visual_keyword", "technology"),
            scene["scene_number"],
            output_dir
        )
        paths.append(path)

        # Small delay between API calls to stay well within rate limits
        time.sleep(0.5)

    return paths
