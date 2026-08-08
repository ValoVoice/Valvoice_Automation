import asyncio
import argparse
import os
import json
import sys
import time
import shutil
import datetime

try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')
except (AttributeError, OSError):
    pass

import config
import settings

from scripts.generate_script import generate_script
from scripts.select_assets import select_assets_for_script, select_bgm
from scripts.validate_content import validate_script_content, validate_metadata, validate_bgm, post_render_validation
from scripts.generate_audio import generate_audio_for_scenes
from scripts.render_video import render_short
from scripts.generate_metadata import generate_platform_metadata

def sanitize_job_id(topic: str) -> str:
    safe = topic[:30].strip()
    safe = "".join(c if c.isalnum() or c in (" ", "-") else "" for c in safe)
    return safe.replace(" ", "_")

def write_obsidian_frontmatter(job_id: str, topic: str, script: dict, metadata: dict, video_path: str, validation_status: str):
    timestamp = datetime.datetime.now().isoformat()
    # Write to ValVoice/Content/Pending
    pending_dir = os.path.join(config.PROJECT_ROOT, "ValVoice", "Content", "Pending")
    os.makedirs(pending_dir, exist_ok=True)
    
    md_path = os.path.join(pending_dir, f"{job_id}.md")
    content = f"""---
content_id: {job_id}
generation_timestamp: {timestamp}
generation_model: {settings.SCRIPT_MODEL}
prompt_version: v2.0
validation_status: {validation_status}
validation_timestamp: {timestamp}
status: pending-review
topic: "{topic}"
video_path: "{video_path}"
---

# {script.get("title", job_id)}

## Script
```json
{json.dumps(script, indent=2)}
```

## Platform Metadata
```json
{json.dumps(metadata, indent=2)}
```
"""
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(content)
    return md_path

async def run_pipeline(topic: str) -> dict:
    job_id = sanitize_job_id(topic)
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    unique_id = f"VV_{job_id}_{timestamp}"
    
    print(f"\n{'='*60}")
    print(f"  VALVOICE CONTENT GENERATION: {topic}")
    print(f"  Job ID: {unique_id}")
    print(f"{'='*60}\n")
    
    # 1. Generate Script
    print("[1/8] Generating Script...")
    script = generate_script(topic)
    
    # 2. Local Asset Selection
    print("\n[2/8] Selecting Local Assets...")
    script = select_assets_for_script(script)
    
    # 3. Pre-Render Validation
    print("\n[3/8] Pre-Render Content Validation...")
    val_status = validate_script_content(script)
    print(f"  ✓ Script Validation Status: {val_status}")
    
    bgm_track = select_bgm()
    if bgm_track:
        if not validate_bgm(bgm_track):
            print(f"  [Validation FAIL] BGM track not in approved folder: {bgm_track}")
            val_status = "FAIL"
    
    if val_status != "PASS":
        md_path = write_obsidian_frontmatter(unique_id, topic, script, {}, "", val_status)
        raise RuntimeError(f"Pre-Render Validation blocked execution (Status: {val_status}). Traceability: {md_path}")
        
    # 4. Generate Audio (Edge-TTS)
    print("\n[4/8] Generating Edge-TTS Narration...")
    audio_path = os.path.join(config.AUDIO_DIR, f"{unique_id}.mp3")
    srt_path = os.path.join(config.SUBTITLES_DIR, f"{unique_id}.srt")
    os.makedirs(config.AUDIO_DIR, exist_ok=True)
    os.makedirs(config.SUBTITLES_DIR, exist_ok=True)
    
    audio_info = await generate_audio_for_scenes(script["scenes"], audio_path, srt_path)
    
    # 5. FFmpeg Render
    print("\n[5/8] Rendering Video...")
    os.makedirs(config.OUTPUT_DIR, exist_ok=True)
    output_path = os.path.join(config.OUTPUT_DIR, f"{unique_id}.mp4")
    
    scene_paths = [s["selected_asset"] for s in script["scenes"]]
    scene_durations = audio_info.get("scene_durations", [s.get("duration_seconds", 4) for s in script["scenes"]])
    
    output_path = render_short(scene_paths, scene_durations, audio_path, srt_path, output_path, bgm_track)
    
    # 6. Post-Render Validation
    print("\n[6/8] Post-Render Validation...")
    if not post_render_validation(output_path):
        val_status = "HUMAN_REVIEW_REQUIRED"
        
    # 7. Generate Platform Metadata
    print("\n[7/8] Generating Platform Metadata...")
    metadata = generate_platform_metadata(script)
    meta_status = validate_metadata(json.dumps(metadata))
    print(f"  ✓ Metadata Validation Status: {meta_status}")
    if meta_status != "PASS":
        val_status = "HUMAN_REVIEW_REQUIRED"
        
    # 8. Obsidian Traceability
    print("\n[8/8] Writing to Obsidian Knowledge Base...")
    md_path = write_obsidian_frontmatter(unique_id, topic, script, metadata, output_path, val_status)
    print(f"  ✓ Traceability saved: {md_path}")
    
    print(f"\n{'='*60}")
    print(f"  ✓ JOB COMPLETE: {unique_id}")
    print(f"  ✓ Video: {output_path}")
    print(f"  ✓ Status: {val_status}")
    print(f"{'='*60}")
    
    return {"job_id": unique_id, "video_path": output_path, "status": val_status}

def load_topics(filepath: str) -> list:
    topics = []
    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip() and not line.startswith("#"):
                topics.append(line.strip())
    return topics

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--topic", type=str)
    parser.add_argument("--topics-file", type=str)
    args = parser.parse_args()
    
    if not args.topic and not args.topics_file:
        parser.print_help()
        sys.exit(1)
        
    topics = [args.topic] if args.topic else load_topics(args.topics_file)
    
    for t in topics:
        try:
            asyncio.run(run_pipeline(t))
        except Exception as e:
            print(f"Pipeline failed for topic '{t}': {e}")
            
if __name__ == "__main__":
    main()
