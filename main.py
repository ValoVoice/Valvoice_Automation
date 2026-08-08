"""
YouTube Shorts Automation — Local CLI Entry Point

Usage:
    python main.py --topic "How attention mechanism works in transformers"
    python main.py --topics-file topics.txt
    python main.py --topics-file topics.txt --count 3
    python main.py --script-only --topic "test topic"
    python main.py --topic "topic" --skip-keyword-check
"""

import asyncio
import argparse
import os
import json
import sys
import time
import shutil
import requests
import random

# Fix Windows console encoding — cp1252 can't print Unicode symbols.
# Reconfigure stdout/stderr to UTF-8 with error replacement so
# emoji and special chars degrade gracefully instead of crashing.
try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')
except (AttributeError, OSError):
    pass  # Not all environments support reconfigure

import config
import settings

from scripts.generate_script import generate_script
from scripts.generate_audio import generate_audio, generate_audio_for_scenes, build_full_narration
from scripts.fetch_assets import fetch_all_assets
from scripts.render_video import render_short


# ── YouTube Keyword Validation ──
# Checks if a topic has actual search demand before wasting API calls.
# Uses YouTube's autocomplete endpoint — free, no API key needed.

def check_keyword_demand(topic: str) -> dict:
    """
    Check if a topic has YouTube search demand via autocomplete suggestions.
    Returns dict with 'has_demand' bool and 'suggestions' list.
    
    Uses the unofficial suggestqueries.google.com endpoint.
    Free, no API key, but unofficial — may break without notice.
    """
    try:
        url = "https://suggestqueries.google.com/complete/search"
        params = {
            "client": "firefox",
            "ds": "yt",
            "q": topic,
            "hl": "en"
        }
        response = requests.get(url, params=params, timeout=5,
                                headers={"User-Agent": "Mozilla/5.0"})
        response.raise_for_status()
        data = response.json()

        # Response format: [query, [suggestion1, suggestion2, ...]]
        suggestions = data[1] if len(data) > 1 else []
        return {
            "has_demand": len(suggestions) > 0,
            "suggestions": suggestions[:5],
            "query": topic
        }
    except Exception:
        # If the endpoint fails, don't block the pipeline — just skip the check
        return {"has_demand": True, "suggestions": [], "query": topic}


def sanitize_job_id(topic: str) -> str:
    """Create a safe filename from a topic string."""
    safe = topic[:30].strip()
    safe = "".join(c if c.isalnum() or c in (" ", "-") else "" for c in safe)
    safe = safe.replace(" ", "_")
    return safe


def apply_ab_split(scenes: list, measured_durations: list) -> tuple[list, list]:
    """Applies A/B splitting to scenes longer than MAX_SCENE_DURATION_BEFORE_SPLIT."""
    render_scenes = []
    render_durations = []
    
    for idx, scene in enumerate(scenes):
        dur = measured_durations[idx] if idx < len(measured_durations) else float(scene["duration_seconds"])
        if dur > settings.MAX_SCENE_DURATION_BEFORE_SPLIT:
            print(f"  [!] Splitting scene {scene['scene_number']} ({dur:.1f}s) into two visual segments for better retention.")
            # Create first half
            scene_a = scene.copy()
            scene_a["scene_number"] = f"{scene['scene_number']}a"
            
            # Create second half
            scene_b = scene.copy()
            scene_b["scene_number"] = f"{scene['scene_number']}b"
            
            # Safe assignment of visual keywords
            keywords = scene.get("visual_keywords", ["technology"])
            if isinstance(keywords, str):
                keywords = [keywords]
            
            scene_a["visual_keyword"] = keywords[0] if len(keywords) > 0 else "technology"
            scene_b["visual_keyword"] = keywords[1] if len(keywords) > 1 else scene_a["visual_keyword"]
            
            render_scenes.extend([scene_a, scene_b])
            render_durations.extend([dur / 2.0, dur / 2.0])
        else:
            keywords = scene.get("visual_keywords", ["technology"])
            if isinstance(keywords, str):
                keywords = [keywords]
            scene["visual_keyword"] = keywords[0] if len(keywords) > 0 else "technology"
            render_scenes.append(scene)
            render_durations.append(dur)
            
    return render_scenes, render_durations


def with_retry(func, *args, retries=1, delay=5, **kwargs):
    """Simple retry wrapper — one retry after a short delay."""
    for attempt in range(retries + 1):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            if attempt < retries:
                print(f"  [retry] {func.__name__} failed ({e}), retrying in {delay}s...")
                time.sleep(delay)
            else:
                raise

async def async_with_retry(func, *args, retries=1, delay=5, **kwargs):
    """Async variant of simple retry wrapper."""
    for attempt in range(retries + 1):
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            if attempt < retries:
                print(f"  [retry] {func.__name__} failed ({e}), retrying in {delay}s...")
                import asyncio
                await asyncio.sleep(delay)
            else:
                raise


async def run_pipeline(topic: str) -> dict:
    """
    Full pipeline: Script → Audio → Assets → Render → Save locally.
    No upload. You review and upload manually.
    """
    job_id = sanitize_job_id(topic)
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    unique_id = f"{job_id}_{timestamp}"

    asset_dir = os.path.join(config.VIDEO_ASSETS_DIR, unique_id)
    audio_path = os.path.join(config.AUDIO_DIR, f"{unique_id}.mp3")
    srt_path = os.path.join(config.SUBTITLES_DIR, f"{unique_id}.srt")

    try:
        success = False
        print(f"\n{'='*60}")
        print(f"  GENERATING: {topic}")
        print(f"  Job ID: {unique_id}")
        print(f"{'='*60}\n")

        # ── Step 1: Generate Script via Gemini ──
        print("[1/5] Generating script via Gemini...")
        try:
            script = with_retry(generate_script, topic)
        except Exception as e:
            print(f"  ✗ Script generation failed: {e}")
            raise

        # Save script JSON for reference
        os.makedirs(config.GENERATED_SCRIPTS_DIR, exist_ok=True)
        script_path = os.path.join(config.GENERATED_SCRIPTS_DIR, f"{unique_id}.json")
        with open(script_path, "w", encoding="utf-8") as f:
            json.dump(script, f, indent=2, ensure_ascii=False)
        print(f"  ✓ Script saved: {script_path}")
        print(f"  ✓ Title: {script.get('title', 'N/A')}")
        print(f"  ✓ Scenes: {len(script.get('scenes', []))}")

        # ── Step 2: Generate Audio via Chatterbox-TTS ──
        print("\n[2/5] Generating audio via Chatterbox-TTS...")

        os.makedirs(config.AUDIO_DIR, exist_ok=True)
        os.makedirs(config.SUBTITLES_DIR, exist_ok=True)

        try:
            # Per-scene generation
            audio_info = await async_with_retry(
                generate_audio_for_scenes,
                scenes=script["scenes"],
                output_path=audio_path,
                srt_path=srt_path
            )
        except Exception as e:
            print(f"  ✗ Audio generation failed: {e}")
            raise
        print(f"  ✓ Audio: {audio_path}")
        print(f"  ✓ Subtitles: {srt_path}")

        measured_scene_durations = []
        if isinstance(audio_info, dict):
            measured_scene_durations = audio_info.get("scene_durations", [])
            audio_duration = audio_info.get("audio_duration")
            if audio_duration:
                print(f"  ✓ Measured audio duration: {audio_duration:.2f}s")
                if audio_duration > 58:
                    raise ValueError(
                        f"TTS audio is {audio_duration:.2f}s, which is too close to or over "
                        "the 60s Shorts limit. Regenerate with a shorter topic/script."
                    )

        # ── Phase 3 Polish: A/B Visual Splitting ──
        render_scenes, render_durations = apply_ab_split(script["scenes"], measured_scene_durations)

        # ── Step 3: Download B-Roll from Pexels ──
        print("\n[3/5] Downloading b-roll from Pexels...")
        os.makedirs(asset_dir, exist_ok=True)

        try:
            asset_paths = fetch_all_assets(render_scenes, asset_dir)
        except Exception as e:
            print(f"  ✗ Asset download failed: {e}")
            raise

        # Filter out failed downloads
        valid_scenes = []
        valid_paths = []
        valid_scene_durations = []
        for idx, (scene, path) in enumerate(zip(render_scenes, asset_paths)):
            if path and os.path.exists(path):
                valid_scenes.append(scene)
                valid_paths.append(path)
                valid_scene_durations.append(render_durations[idx])

        print(f"  ✓ Downloaded {len(valid_paths)}/{len(render_scenes)} clips")

        if len(valid_scenes) < 2:
            raise ValueError(
                f"Only {len(valid_scenes)} clips downloaded. Need at least 2. "
                "Try different visual_search terms or check your Pexels API key."
            )

        if len(valid_scenes) != len(render_scenes):
            raise ValueError(
                f"Downloaded {len(valid_scenes)}/{len(render_scenes)} clips. "
                "Cannot safely render because visual timing relies on exact clip counts."
            )

        # ── Step 4: Render Final Video via FFmpeg ──
        print("\n[4/5] Rendering video via FFmpeg...")
        os.makedirs(config.OUTPUT_DIR, exist_ok=True)
        output_path = os.path.join(config.OUTPUT_DIR, f"{unique_id}.mp4")

        try:
            render_short(
                scene_paths=valid_paths,
                scene_durations=valid_scene_durations,
                audio_path=audio_path,
                srt_path=srt_path,
                output_path=output_path
            )
        except Exception as e:
            print(f"  ✗ Render failed: {e}")
            raise

        success = True

    except Exception as e:
        success = False
        print(f"\n[FATAL] Pipeline failed at: {e}\n")
        raise
    finally:
        # ── Step 5: Cleanup ──
        if success:
            print("\n[5/5] Cleaning up raw assets...")
            try:
                shutil.rmtree(asset_dir, ignore_errors=True)
                if os.path.exists(audio_path):
                    os.remove(audio_path)
                if os.path.exists(srt_path):
                    os.remove(srt_path)
                print(f"  ✓ Deleted raw clips and temp audio/subs")
            except OSError as e:
                print(f"  ⚠ Cleanup failed: {e}")
        else:
            print(f"\n[DEBUG] Job failed — preserving artifacts at {asset_dir} for inspection")

# ── Done ──
    file_size = os.path.getsize(output_path) / (1024 * 1024)
    print(f"\n{'='*60}")
    print(f"  ✓ VIDEO READY: {output_path}")
    print(f"  ✓ Size: {file_size:.1f} MB")
    print(f"  ✓ Title: {script.get('title', 'N/A')}")
    print(f"  ✓ Tags: {', '.join(script.get('tags', []))}")
    print(f"{'='*60}")
    print(f"\n  → Open the artifacts/output/ folder, review the video, and upload to YouTube Studio.")
    print(f"  ⚠ REMINDER: Enable 'Altered or synthetic content' label before publishing!")

    return {
        "job_id": unique_id,
        "title": script["title"],
        "description": script.get("description", ""),
        "tags": script.get("tags", []),
        "video_path": output_path,
        "script_path": script_path,
    }


def load_topics_from_file(filepath: str) -> list:
    """Read topics from a text file, one per line. Skips empty lines and comments."""
    topics = []
    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                topics.append(line)
    return topics


def _run_script_only(topic: str) -> dict:
    """Generate only the script JSON — no audio, no video. For prompt testing."""
    job_id = sanitize_job_id(topic)
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    unique_id = f"{job_id}_{timestamp}"

    print(f"\n  Generating script for: {topic}")
    script = with_retry(generate_script, topic)

    os.makedirs(config.GENERATED_SCRIPTS_DIR, exist_ok=True)
    script_path = os.path.join(config.GENERATED_SCRIPTS_DIR, f"{unique_id}.json")
    with open(script_path, "w", encoding="utf-8") as f:
        json.dump(script, f, indent=2, ensure_ascii=False)

    print(f"  ✓ Saved: {script_path}")
    print(f"  ✓ Title: {script.get('title', 'N/A')}")
    print(f"\n  Script preview:")
    print(json.dumps(script, indent=2))

    return {"job_id": unique_id, "title": script["title"], "script_path": script_path, "video_path": script_path}


def main():
    parser = argparse.ArgumentParser(
        description="YouTube Shorts Generator — Local CLI",
        epilog="Example: python main.py --topic \"How transformers work\""
    )
    parser.add_argument(
        "--topic",
        type=str,
        help="Single topic to generate a video for"
    )
    parser.add_argument(
        "--topics-file",
        type=str,
        help="Path to a .txt file with one topic per line"
    )
    parser.add_argument(
        "--count",
        type=int,
        default=1,
        help="Number of topics to process from the file (default: 1)"
    )
    parser.add_argument(
        "--script-only",
        action="store_true",
        help="Only generate the script JSON (no audio, no video). Good for testing prompts"
    )
    parser.add_argument(
        "--skip-keyword-check",
        action="store_true",
        help="Skip YouTube autocomplete keyword demand check"
    )

    args = parser.parse_args()

    # Validate args
    if not args.topic and not args.topics_file:
        parser.print_help()
        print("\n✗ Error: Provide either --topic or --topics-file")
        sys.exit(1)

    # Validate environment
    if not settings.GEMINI_API_KEY:
        print("✗ Error: GEMINI_API_KEY not set. Copy .env.example to .env and add your key.")
        sys.exit(1)
    if not args.script_only and not settings.PEXELS_API_KEY:
        print("✗ Error: PEXELS_API_KEY not set. Copy .env.example to .env and add your key.")
        sys.exit(1)

    # Build topic list
    if args.topic:
        topics = [args.topic]
    else:
        if not os.path.exists(args.topics_file):
            print(f"✗ Error: Topics file not found: {args.topics_file}")
            sys.exit(1)
        topics = load_topics_from_file(args.topics_file)
        if not topics:
            print(f"✗ Error: No topics found in {args.topics_file}")
            sys.exit(1)
        topics = topics[:args.count]

    # ── Keyword demand check ──
    if not args.skip_keyword_check:
        print("\n[*] Checking YouTube search demand...")
        for topic in topics:
            result = check_keyword_demand(topic)
            if result["has_demand"]:
                print(f"  ✓ '{topic}' — {len(result['suggestions'])} autocomplete suggestions")
            else:
                print(f"  ⚠ '{topic}' — NO autocomplete suggestions. Consider rephrasing for better SEO.")
        print()

    # Run pipeline for each topic
    mode = "script(s)" if args.script_only else "video(s)"
    print(f"▶ Generating {len(topics)} {mode}...\n")
    results = []
    for i, topic in enumerate(topics, 1):
        print(f"\n--- {'Script' if args.script_only else 'Video'} {i}/{len(topics)} ---")
        try:
            if args.script_only:
                result = _run_script_only(topic)
            else:
                result = asyncio.run(run_pipeline(topic))
            results.append(result)
        except Exception as e:
            print(f"\n✗ Failed for: {topic}")
            print(f"  Error: {e}")
            continue

    # Summary
    print(f"\n\n{'='*60}")
    print(f"  SUMMARY: {len(results)}/{len(topics)} {'scripts' if args.script_only else 'videos'} generated successfully")
    print(f"{'='*60}")
    for r in results:
        print(f"  ✓ {r['video_path']}  →  {r['title']}")
    if results and not args.script_only:
        print(f"\n  → Open the artifacts/output/ folder to review your videos.")
        print(f"  → Upload the good ones to YouTube Studio manually.")
        print(f"  ⚠ ALWAYS enable 'Altered or synthetic content' label before publishing!")


if __name__ == "__main__":
    main()
