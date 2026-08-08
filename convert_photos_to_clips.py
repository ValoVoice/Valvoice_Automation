"""
Converts all images in raw/promo_photos/ into placeholder video clips
in raw/obs_clips/, ready for main_promo.py to consume.

Usage:
    python convert_photos_to_clips.py
    python convert_photos_to_clips.py --duration 5 --zoom
"""
import subprocess
import os
import argparse
import glob
import json
import sys

# Fix Windows console symbol output
try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except (AttributeError, OSError):
    pass

import settings

SOURCE_DIR = os.path.join("raw", "promo_photos")
OUTPUT_DIR = os.path.join("raw", "obs_clips")


def convert_image_to_clip(image_path: str, output_path: str, duration: int = 4, zoom: bool = False):
    # Universal UI Fit + Glassmorphic Box-Blur Background:
    # Preserves 100% of horizontal UI width without cropping left/right sidebars/dock drawers.
    base_filters = (
        "split[bg][fg];"
        "[bg]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,boxblur=25:10,colorchannelmixer=rr=0.4:gg=0.4:bb=0.4[bg_out];"
        "[fg]scale=1080:1920:force_original_aspect_ratio=decrease[fg_out];"
        "[bg_out][fg_out]overlay=(W-w)/2:(H-h)/2,setsar=1"
    )
    
    if zoom:
        vf = f"{base_filters},zoompan=z='min(zoom+0.001,1.05)':d={duration * 30}:s=1080x1920:fps=30"
    else:
        vf = base_filters
    
    cmd = [
        "ffmpeg", "-y",
        "-loop", "1",
        "-i", image_path,
        "-t", str(duration),
        "-vf", vf,
        "-c:v", settings.ENCODER,
        "-pix_fmt", "yuv420p",
        "-r", "30",
        output_path
    ]
    
    # Fallback to libx264 if NVENC hardware encoder fails on static images
    try:
        subprocess.run(cmd, check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as e:
        if settings.ENCODER == "h264_nvenc":
            print("    Warning: NVENC failed on still image conversion, falling back to CPU libx264...")
            cmd[cmd.index("h264_nvenc")] = "libx264"
            subprocess.run(cmd, check=True, capture_output=True, text=True)
        else:
            raise RuntimeError(f"FFmpeg error converting {image_path}: {e.stderr}")

    print(f"  ✓ Created: {output_path}")
    return output_path


def main():
    parser = argparse.ArgumentParser(description="Convert screenshots into vertical video stand-ins for promo testing.")
    parser.add_argument("--duration", type=int, default=4, help="Clip duration in seconds")
    parser.add_argument("--zoom", action="store_true", help="Add subtle Ken Burns zoom effect")
    args = parser.parse_args()

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    os.makedirs(SOURCE_DIR, exist_ok=True)

    extensions = ("*.png", "*.jpg", "*.jpeg", "*.webp", "*.PNG", "*.JPG", "*.JPEG")
    images = []
    for ext in extensions:
        images.extend(glob.glob(os.path.join(SOURCE_DIR, ext)))
    images = sorted(list(set(images)))

    if not images:
        print(f"\n[!] No photos found in '{SOURCE_DIR}'!")
        print(f"    Action Required: Save your Acrylic screenshots into '{SOURCE_DIR}' and re-run this command.")
        return

    print(f"\n{'='*60}")
    print(f"  Converting {len(images)} photo(s) into promo stand-in videos...")
    print(f"  Encoder: {settings.ENCODER} | Duration: {args.duration}s | Zoom: {args.zoom}")
    print(f"{'='*60}\n")

    converted_clips = []
    for image_path in images:
        name = os.path.splitext(os.path.basename(image_path))[0]
        output_path = os.path.join(OUTPUT_DIR, f"{name}_placeholder.mp4").replace("\\", "/")
        try:
            converted_clips.append(convert_image_to_clip(image_path, output_path, duration=args.duration, zoom=args.zoom))
        except Exception as e:
            print(f"  ✗ Failed to convert {image_path}: {e}")

    print(f"\nDone! {len(converted_clips)} placeholder clip(s) ready in '{OUTPUT_DIR}/'.")

    # Auto-generate a ready-to-run JSON config curated specifically for the Acrylic UI showcase!
    if converted_clips:
        # Define intelligent mapping based on known Acrylic UI images
        curated_map = {
            "Showcase1_placeholder.mp4": {"text": "Why is your Chrome still on default?", "dur": 3.5},
            "Showcase2_placeholder.mp4": {"text": "Quick links dock. Zero clutter.", "dur": 4.0},
            "Showcase5_placeholder.mp4": {"text": "Built-in Pomodoro & task timer.", "dur": 4.0},
            "Showcase3_placeholder.mp4": {"text": "Custom fonts & dynamic themes.", "dur": 4.0},
            "Marquee promo tile_placeholder.mp4": {"text": "Get Acrylic — free on Web Store!", "dur": 4.5},
        }

        clips_config = []
        # Try inserting in our narrative order first
        for name, info in curated_map.items():
            path = os.path.join(OUTPUT_DIR, name).replace("\\", "/")
            if any(c.endswith(name) for c in converted_clips):
                clips_config.append({
                    "path": path,
                    "overlay_text": info["text"],
                    "duration_seconds": info["dur"]
                })

        # If standard filenames didn't match, fall back to sequential order
        if not clips_config:
            sample_hooks = [
                "Why is your Chrome still on default?",
                "Meet Acrylic — sleek & fast.",
                "Custom widgets. Zero clutter.",
                "Instant theme switching.",
                "Designed for focus."
            ]
            clips_config = [
                {
                    "path": cp,
                    "overlay_text": sample_hooks[i] if i < len(sample_hooks) else f"Feature Highlight #{i+1}",
                    "duration_seconds": float(args.duration)
                } for i, cp in enumerate(converted_clips) if "300x188" not in cp
            ]

        config_data = {
            "title": "Acrylic UI Showcase (Photo Stand-ins)",
            "output_name": "acrylic_photo_promo",
            "spoken_hook": "Why is your Chrome still on the default new tab.",
            "generate_voice": True,
            "clips": clips_config
        }
        out_config = "promo_from_photos.json"
        with open(out_config, "w", encoding="utf-8") as f:
            json.dump(config_data, f, indent=2)
        print(f"\n{'='*60}")
        print(f"  ✓ Auto-generated promo configuration: {out_config}")
        print(f"  → To run your end-to-end mechanical test instantly, run:")
        print(f"     python main_promo.py --config {out_config}")
        print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
