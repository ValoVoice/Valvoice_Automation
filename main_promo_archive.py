"""
YouTube Shorts Automation — Promo & Product Reveal Pipeline (main_promo.py)

Dedicated entry point for product videos (e.g., Acrylic Chrome Extension):
- Ingests local screen recordings directly (e.g., OBS captures), skipping Pexels stock b-roll entirely.
- Bakes punchy text overlay hooks directly onto video frames using FFmpeg drawtext.
- Uses Chatterbox-TTS exclusively for short, emotive spoken hooks (3-5s), avoiding long-form degradation.
- Explicitly skips word-level SRT subtitle burn-in (text overlays carry the message).
- Reuses tested NVENC encoder & transition logic from scripts/render_video.py without duplication.

Usage:
    python main_promo.py --init-template
    python main_promo.py --config acrylic_promo.json
    python main_promo.py --clips "obs/clip1.mp4,obs/clip2.mp4" --overlays "Why default Chrome?,Meet Acrylic workspace." --hook-text "Why is your Chrome still on the default new tab."
"""

import argparse
import asyncio
import json
import os
import sys
import time
import shutil

# Fix Windows console encoding for symbol printing
try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')
except (AttributeError, OSError):
    pass

import config
import settings
from scripts.generate_audio import generate_audio
from scripts.render_video import render_promo

TEMPLATE_FILENAME = "acrylic_promo_example.json"
EXAMPLE_TEMPLATE = {
    "title": "Why is your Chrome still on the default new tab?",
    "output_name": "acrylic_extension_promo",
    "spoken_hook": "Why is your Chrome still on the default new tab.",
    "generate_voice": True,
    "clips": [
        {
            "path": "raw/obs_clips/boring_default_tab.mp4",
            "overlay_text": "Why is your Chrome still on default?",
            "duration_seconds": 3.5
        },
        {
            "path": "raw/obs_clips/acrylic_reveal_animation.mp4",
            "overlay_text": "Meet Acrylic — the aesthetic workspace.",
            "duration_seconds": 4.5
        },
        {
            "path": "raw/obs_clips/widgets_customization.mp4",
            "overlay_text": "Custom widgets. Zero clutter.",
            "duration_seconds": 5.0
        }
    ]
}


def create_template():
    """Generates an example config template for OBS screen recording promos."""
    path = os.path.abspath(TEMPLATE_FILENAME)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(EXAMPLE_TEMPLATE, f, indent=2)
    print(f"\n{'='*60}")
    print(f"  ✓ Template configuration saved to: {path}")
    print(f"{'='*60}")
    print("\nNext steps:")
    print("  1. Record your Acrylic screen demos via OBS and save them in 'raw/obs_clips/'.")
    print(f"  2. Edit '{TEMPLATE_FILENAME}' with your exact file paths and overlay texts.")
    print(f"  3. Run: python main_promo.py --config {TEMPLATE_FILENAME}\n")


async def run_promo_pipeline(config_data: dict) -> dict:
    """Executes the promo video creation pipeline."""
    job_name = config_data.get("output_name", "promo_video").strip().replace(" ", "_")
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    unique_id = f"{job_name}_{timestamp}"

    os.makedirs(config.AUDIO_DIR, exist_ok=True)
    os.makedirs(config.OUTPUT_DIR, exist_ok=True)

    hook_text = config_data.get("spoken_hook", "").strip()
    generate_voice = config_data.get("generate_voice", bool(hook_text))
    clip_configs = config_data.get("clips", [])

    if not clip_configs:
        raise ValueError("No video clips specified in configuration. Please provide local OBS recording paths.")

    print(f"\n{'='*60}")
    print(f"  PROMO PIPELINE: {config_data.get('title', job_name)}")
    print(f"  Job ID: {unique_id}")
    print(f"{'='*60}\n")

    # ── Step 1: Validate Local OBS Footage Exists ──
    print("[1/3] Checking input video clips...")
    valid_clips = 0
    for idx, clip in enumerate(clip_configs, 1):
        c_path = clip.get("path", "")
        if not os.path.exists(c_path):
            print(f"  ✗ Missing required OBS clip [{idx}]: '{c_path}'")
        else:
            print(f"  ✓ Verified clip [{idx}]: {c_path} ({clip.get('duration_seconds', 'natural')}s)")
            valid_clips += 1

    if valid_clips != len(clip_configs):
        raise FileNotFoundError(
            f"\nOnly {valid_clips}/{len(clip_configs)} video clips found on disk.\n"
            "Action Required: You must record real OBS footage of Acrylic before running this pipeline.\n"
            "Nothing will match your script until real screen recordings exist as the visual source!"
        )

    # ── Step 2: Generate Spoken Hook via Chatterbox (Optional, 3-5s limit) ──
    hook_audio_path = None
    if generate_voice and hook_text:
        print("\n[2/3] Generating punchy 3-5s spoken hook via Chatterbox-TTS...")
        print(f"  Hook Text: \"{hook_text}\"")
        hook_audio_path = os.path.join(config.AUDIO_DIR, f"{unique_id}_hook.mp3")
        try:
            # Use single-block generate_audio optimized for quick hooks
            await generate_audio(text=hook_text, output_path=hook_audio_path, srt_path=None)
            print(f"  ✓ Spoken hook audio saved: {hook_audio_path}")
        except Exception as e:
            print(f"  ⚠ Audio generation failed ({e}). Continuing without spoken hook...")
            hook_audio_path = None
    else:
        print("\n[2/3] Skipping spoken voice generation (silent video for native platform trending audio)...")

    # ── Step 3: Render Video via Shared Encoder Logic ──
    print("\n[3/3] Rendering promo video (text overlays + silent background for native audio + NVENC)...")
    output_path = os.path.join(config.OUTPUT_DIR, f"{unique_id}.mp4")

    try:
        render_promo(
            clip_configs=clip_configs,
            output_path=output_path,
            hook_audio_path=hook_audio_path
        )
    finally:
        # Cleanup temp hook audio
        if hook_audio_path and os.path.exists(hook_audio_path):
            try:
                os.remove(hook_audio_path)
            except OSError:
                pass

    file_size = os.path.getsize(output_path) / (1024 * 1024) if os.path.exists(output_path) else 0.0
    print(f"\n{'='*60}")
    print(f"  ✓ PROMO VIDEO READY: {output_path}")
    print(f"  ✓ Size: {file_size:.1f} MB")
    print(f"  ✓ Title: {config_data.get('title', 'Acrylic Promo')}")
    print(f"{'='*60}")
    print("\n  → Open the artifacts/output/ folder to review your video.")
    print("  ⚠ REMINDER: Enable 'Altered or synthetic content' label before publishing!")

    return {
        "job_id": unique_id,
        "title": config_data.get("title", job_name),
        "video_path": output_path
    }


def main():
    parser = argparse.ArgumentParser(
        description="YouTube Shorts Generator — Promo & Screen Capture Pipeline",
        epilog="Example: python main_promo.py --config acrylic_promo.json"
    )
    parser.add_argument(
        "--init-template",
        action="store_true",
        help="Generate a starter config template file (acrylic_promo_example.json) and exit"
    )
    parser.add_argument(
        "--config",
        type=str,
        help="Path to a promo JSON configuration file"
    )
    parser.add_argument(
        "--clips",
        type=str,
        help="Comma-separated list of local OBS video file paths"
    )
    parser.add_argument(
        "--overlays",
        type=str,
        help="Pipe-separated ('|') or comma-separated list of text overlays corresponding to --clips"
    )
    parser.add_argument(
        "--hook-text",
        type=str,
        help="Short spoken hook text (3-5 seconds) for Chatterbox TTS"
    )

    args = parser.parse_args()

    if args.init_template:
        create_template()
        sys.exit(0)

    # If neither --config nor CLI args given, show help and guide user
    if not args.config and not args.clips:
        parser.print_help()
        print("\n✗ Error: Please specify either --config <file.json>, --clips <path1,path2>, or run --init-template")
        sys.exit(1)

    config_data = {}

    if args.config:
        if not os.path.exists(args.config):
            print(f"✗ Error: Config file not found: {args.config}")
            sys.exit(1)
        try:
            with open(args.config, "r", encoding="utf-8") as f:
                config_data = json.load(f)
        except json.JSONDecodeError as e:
            print(f"✗ Error parsing JSON in {args.config}: {e}")
            sys.exit(1)
    else:
        # Build config dynamically from CLI args
        clip_paths = [c.strip() for c in args.clips.split(",") if c.strip()]
        overlays = []
        if args.overlays:
            sep = "|" if "|" in args.overlays else ","
            overlays = [o.strip() for o in args.overlays.split(sep)]

        clips_list = []
        for i, p in enumerate(clip_paths):
            ov_text = overlays[i] if i < len(overlays) else ""
            clips_list.append({"path": p, "overlay_text": ov_text, "duration_seconds": 4.0})

        config_data = {
            "title": "CLI Promo Render",
            "output_name": "cli_promo",
            "spoken_hook": args.hook_text or "",
            "generate_voice": bool(args.hook_text),
            "clips": clips_list
        }

    try:
        asyncio.run(run_promo_pipeline(config_data))
    except Exception as e:
        print(f"\n✗ Pipeline failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
