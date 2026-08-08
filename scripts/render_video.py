import subprocess
import os
import shutil
import random
from dotenv import load_dotenv

load_dotenv()
import config
import settings

if settings.ENCODER == "h264_nvenc":
    ENCODE_FLAGS = ["-c:v", "h264_nvenc", "-preset", "p4", "-cq", "23", "-gpu", "0"]
    FINAL_ENCODE_FLAGS = ["-c:v", "h264_nvenc", "-preset", "p4", "-cq", "20", "-gpu", "0"]
else:
    ENCODE_FLAGS = ["-c:v", "libx264", "-crf", "23", "-preset", "fast"]
    FINAL_ENCODE_FLAGS = ["-c:v", "libx264", "-crf", "20", "-preset", "fast"]


def _run_ffmpeg(cmd: list, step_name: str) -> None:
    """Run an FFmpeg command with proper error reporting."""
    try:
        result = subprocess.run(
            cmd,
            check=True,
            capture_output=True,
            text=True
        )
    except subprocess.CalledProcessError as e:
        print(f"  ERROR: FFmpeg failed at: {step_name}")
        print(f"    stderr: {e.stderr[-500:] if e.stderr else 'no output'}")
        raise RuntimeError(f"FFmpeg error during {step_name}: {e.stderr[-200:] if e.stderr else 'unknown'}") from e
    except FileNotFoundError:
        raise RuntimeError(
            "FFmpeg not found. Install it with: winget install ffmpeg\n"
            "Then restart your terminal."
        )


def _get_safe_ffmpeg_path(path: str) -> str:
    """
    Convert file path for FFmpeg filter graph strings on Windows (SRT subs, drawtext fonts).
    FFmpeg requires forward slashes and escaped colons in filter arguments.
    Example: C:\\Users\\HP\\sub.srt -> C\\:/Users/HP/sub.srt
    """
    abs_path = os.path.abspath(path)
    safe = abs_path.replace("\\", "/")
    if len(safe) >= 2 and safe[1] == ":":
        safe = safe[0] + "\\:" + safe[2:]
    return safe


_get_safe_srt_path = _get_safe_ffmpeg_path  # Alias for existing subtitle callers


def _pick_bgm_track() -> str | None:
    """
    Pick a random background music track from the songs/ directory.
    Returns absolute path to the track, or None if no tracks found.

    Supports: .mp3, .wav, .m4a, .ogg
    """
    songs_dir = config.SONGS_DIR
    if not os.path.isdir(songs_dir):
        return None

    valid_extensions = (".mp3", ".wav", ".m4a", ".ogg")
    tracks = [
        os.path.join(songs_dir, f)
        for f in os.listdir(songs_dir)
        if f.lower().endswith(valid_extensions) and os.path.getsize(os.path.join(songs_dir, f)) > 10 * 1024
    ]

    if not tracks:
        return None

    chosen = random.choice(tracks)
    print(f"    BGM: {os.path.basename(chosen)}")
    return os.path.abspath(chosen)


def render_short(
    scene_paths: list,
    scene_durations: list,
    audio_path: str,
    srt_path: str,
    output_path: str
) -> str:
    """
    Full render pipeline using FFmpeg directly:
    1. Extend/trim each clip to match its scene's narration duration
    2. Scale/crop to 1080x1920 (9:16 vertical)
    3. Concatenate with xfade transitions (0.3s cross-fade)
    4. Overlay the Edge-TTS audio track (audio drives final duration)
    5. Mix background music at -20dB (if songs/ folder has tracks)
    6. Burn in subtitles from .srt file
    7. Export with YouTube-optimized encoding flags

    Returns the output file path.
    """

    temp_dir = config.VIDEO_TEMP_DIR
    os.makedirs(temp_dir, exist_ok=True)

    xfade_duration = 0.3  # seconds of cross-fade between clips
    audio_duration = _get_video_duration(audio_path)  # works for audio files too

    # ── Step 1: Process each clip (extend/trim to scene duration + scale/crop) ──
    print(f"    [render] Using {'GPU' if settings.ENCODER == 'h264_nvenc' else 'CPU'} encoder ({settings.ENCODER})")
    print("    Processing clips...")
    processed_clips = []
    clip_count = len(scene_paths)
    for i, (clip_path, target_dur) in enumerate(zip(scene_paths, scene_durations)):
        # Validate clip exists and isn't empty
        if not os.path.exists(clip_path) or os.path.getsize(clip_path) < 1024:
            print(f"    Warning: Skipping invalid clip: {clip_path}")
            continue

        out = os.path.join(temp_dir, f"processed_{i}.mp4")

        # Use the measured TTS scene duration when available. Add the xfade
        # overlap to every clip except the last, because each transition
        # consumes that much visual time during concatenation.
        target_dur = max(float(target_dur), 2.0)
        if clip_count > 1 and i < clip_count - 1:
            target_dur += xfade_duration

        # Check source clip duration to decide if we need to loop
        source_dur = _get_video_duration(clip_path)
        loop_count = 0
        if source_dur > 0 and source_dur < target_dur:
            # Need to loop: calculate how many times to repeat
            import math
            loop_count = math.ceil(target_dur / source_dur) - 1

        cmd = ["ffmpeg", "-y"]
        if loop_count > 0:
            # Loop the clip enough times to cover the target duration
            cmd.extend(["-stream_loop", str(loop_count)])
        cmd.extend([
            "-i", clip_path,
            "-t", str(target_dur),                  # Trim to exact scene duration
            "-vf", (
                "scale=1080:1920:"
                "force_original_aspect_ratio=increase,"
                "crop=1080:1920,"                  # Center-crop to 9:16
                "setsar=1"                         # Fix sample aspect ratio
            ),
            "-r", "30",                            # 30fps standard for Shorts
        ])
        cmd.extend(ENCODE_FLAGS)
        cmd.extend([
            "-an",                                 # Strip original audio
            out
        ])
        _run_ffmpeg(cmd, f"processing clip {i+1} ({target_dur:.2f}s)")
        processed_clips.append(out)

    if len(processed_clips) < 1:
        raise RuntimeError("No clips were successfully processed")

    # ── Step 2: Concatenate clips (with xfade if possible) ──
    concat_out = os.path.join(temp_dir, "concatenated.mp4")

    if len(processed_clips) >= 2:
        # Use xfade for smooth transitions between clips
        print(f"    Concatenating with {xfade_duration}s cross-fade transitions...")
        concat_out = _concat_with_xfade(processed_clips, concat_out, xfade_duration)
    else:
        # Single clip — just copy it
        print("    Single clip, no transitions needed...")
        shutil.copy2(processed_clips[0], concat_out)

    # Guardrail: if measured audio is still longer than the visual stream
    # because of source quirks or rounded durations, clone the last frame so
    # the video stream covers the full narration.
    if audio_duration > 0:
        visual_duration = _get_video_duration(concat_out)
        if visual_duration + 0.05 < audio_duration:
            pad_duration = audio_duration - visual_duration
            print(f"    Extending final visual by {pad_duration:.2f}s to match audio...")
            padded_out = os.path.join(temp_dir, "padded.mp4")
            cmd = [
                "ffmpeg", "-y",
                "-i", concat_out,
                "-vf", f"tpad=stop_mode=clone:stop_duration={pad_duration}",
                "-t", str(audio_duration)
            ]
            cmd.extend(ENCODE_FLAGS)
            cmd.extend([
                "-an",
                padded_out
            ])
            _run_ffmpeg(cmd, "padding visual stream")
            concat_out = padded_out

    # ── Step 3: Add the Edge-TTS audio track ──
    # Audio drives the final duration. We measure the audio length and
    # clamp the output to exactly that duration. This ensures:
    # - No narration gets cut off (old bug: -shortest trimmed to 22s)
    # - No silent trailing video (new: clips can be longer than audio)
    print("    Adding audio track...")
    with_audio = os.path.join(temp_dir, "with_audio.mp4")
    cmd = [
        "ffmpeg", "-y",
        "-i", concat_out,
        "-i", audio_path,
        "-map", "0:v:0",
        "-map", "1:a:0",
        "-c:v", "copy",
        "-c:a", "aac",
        "-b:a", "192k",
    ]
    if audio_duration > 0:
        cmd.extend(["-t", str(audio_duration)])  # Clamp to audio length
    cmd.append(with_audio)
    _run_ffmpeg(cmd, "adding audio")

    # ── Step 3.5: Mix background music (if available) ──
    bgm_track = _pick_bgm_track()
    if bgm_track:
        print("    Mixing background music at -20dB...")
        with_bgm = os.path.join(temp_dir, "with_bgm.mp4")
        cmd = [
            "ffmpeg", "-y",
            "-i", with_audio,
            "-i", bgm_track,
            "-filter_complex", (
                "[1:a]volume=0.1,aloop=loop=-1:size=2e+09[bgm];"  # Loop BGM + set to ~-20dB
                "[0:a][bgm]amix=inputs=2:duration=first:dropout_transition=2[out]"
            ),
            "-map", "0:v",
            "-map", "[out]",
            "-c:v", "copy",
            "-c:a", "aac",
            "-b:a", "192k",
            with_bgm
        ]
        try:
            _run_ffmpeg(cmd, "mixing BGM")
            with_audio = with_bgm  # Use the BGM-mixed version going forward
        except RuntimeError:
            print("    Warning: BGM mixing failed, continuing without background music")

    # ── Step 4: Burn in subtitles + final export ──
    print("    Burning subtitles + final export...")
    
    cmd = [
        "ffmpeg", "-y",
        "-i", with_audio
    ]

    if srt_path and os.path.exists(srt_path) and os.path.getsize(srt_path) > 0:
        safe_srt = _get_safe_srt_path(srt_path)
        cmd.extend([
            "-vf", (
                f"subtitles='{safe_srt}':"
                "force_style='"
                "FontName=Arial,"
                "FontSize=14,"
                "PrimaryColour=&H00FFFFFF,"            # White text
                "OutlineColour=&H00000000,"            # Black outline
                "Outline=2,"
                "Bold=1,"
                "Alignment=2,"                         # Bottom center
                "MarginV=80"                           # Space from bottom edge
                "'"
            )
        ])
    else:
        print("    [render] No subtitles — skipping burn-in")

    cmd.extend(FINAL_ENCODE_FLAGS)
    cmd.extend([
        "-c:a", "copy",
        "-pix_fmt", "yuv420p",                     # Universal player compatibility
        "-movflags", "+faststart",                 # Move moov atom for instant web playback
        output_path
    ])
    _run_ffmpeg(cmd, "final export")

    # ── Cleanup temp files ──
    try:
        shutil.rmtree(temp_dir)
    except OSError:
        pass  # Non-critical, temp files just take up space

    print(f"  Rendered: {output_path}")
    if bgm_track:
        print(f"  BGM: {os.path.basename(bgm_track)}")
    return output_path


def _concat_with_xfade(clips: list, output_path: str, fade_dur: float = 0.3) -> str:
    """
    Concatenate clips with xfade cross-fade transitions.

    For N clips, creates N-1 xfade filters chained together.
    Each clip gets a 0.3s cross-fade into the next.
    
    Falls back to simple concat if xfade fails (e.g., clips too short).
    """
    if len(clips) < 2:
        return clips[0]

    # Build the xfade filter chain
    # For clips A, B, C: [0:v][1:v]xfade=...[v01]; [v01][2:v]xfade=...[v012]
    inputs = " ".join([f"-i {c}" for c in clips])
    
    filter_parts = []
    # Get clip durations for offset calculation
    clip_durations = []
    for clip in clips:
        dur = _get_video_duration(clip)
        clip_durations.append(dur)

    # First xfade
    offset = clip_durations[0] - fade_dur
    if offset < 0.1:
        offset = 0.1
    
    if len(clips) == 2:
        filter_str = f"[0:v][1:v]xfade=transition=fade:duration={fade_dur}:offset={offset}"
    else:
        # Chain xfades for 3+ clips
        filter_str = f"[0:v][1:v]xfade=transition=fade:duration={fade_dur}:offset={offset}[v01]"
        running_offset = offset + clip_durations[1] - fade_dur
        
        for i in range(2, len(clips)):
            prev_label = f"v{''.join(str(x) for x in range(i))}"
            if i == len(clips) - 1:
                # Last one — no output label
                filter_str += f";[{prev_label}][{i}:v]xfade=transition=fade:duration={fade_dur}:offset={running_offset}"
            else:
                curr_label = f"v{''.join(str(x) for x in range(i+1))}"
                filter_str += f";[{prev_label}][{i}:v]xfade=transition=fade:duration={fade_dur}:offset={running_offset}[{curr_label}]"
            running_offset += clip_durations[i] - fade_dur

    cmd = ["ffmpeg", "-y"]
    for clip in clips:
        cmd.extend(["-i", clip])
    cmd.extend([
        "-filter_complex", filter_str,
    ])
    cmd.extend(ENCODE_FLAGS)
    cmd.extend([
        "-an",
        output_path
    ])

    try:
        _run_ffmpeg(cmd, "xfade transitions")
        return output_path
    except RuntimeError:
        print("    Warning: xfade failed, falling back to simple concat...")
        return _simple_concat(clips, output_path)


def _simple_concat(clips: list, output_path: str) -> str:
    """Fallback: simple concat without transitions."""
    temp_dir = os.path.dirname(output_path)
    concat_list = os.path.join(temp_dir, "concat.txt")
    with open(concat_list, "w") as f:
        for clip in clips:
            abs_clip = os.path.abspath(clip).replace("\\", "/")
            f.write(f"file '{abs_clip}'\n")

    cmd = [
        "ffmpeg", "-y",
        "-f", "concat",
        "-safe", "0",
        "-i", concat_list,
        "-c", "copy",
        output_path
    ]
    _run_ffmpeg(cmd, "simple concat")
    return output_path


def _get_video_duration(path: str) -> float:
    """Get video duration in seconds. Tries ffprobe, then ffmpeg -i, then 4.0s default."""
    import re

    # Try 1: ffprobe
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", path],
            capture_output=True, text=True, check=True
        )
        return float(result.stdout.strip())
    except (subprocess.CalledProcessError, ValueError, FileNotFoundError):
        pass

    # Try 2: ffmpeg -i (parse Duration from stderr)
    try:
        result = subprocess.run(
            ["ffmpeg", "-i", path, "-hide_banner"],
            capture_output=True, text=True
        )
        match = re.search(r"Duration:\s*(\d+):(\d+):(\d+)\.(\d+)", result.stderr)
        if match:
            h, m, s, cs = int(match.group(1)), int(match.group(2)), int(match.group(3)), int(match.group(4))
            return h * 3600 + m * 60 + s + cs / 100.0
    except (FileNotFoundError, OSError):
        pass

    return 4.0  # Safe default


def _escape_drawtext_str(text: str) -> str:
    """Escape characters for FFmpeg drawtext filter string on Windows."""
    return text.replace("\\", "\\\\").replace("'", "\\'").replace(":", "\\:").replace("%", "\\%")


def _get_drawtext_font() -> str:
    """Find a system font path formatted safely for Windows FFmpeg drawtext."""
    for font_name in ("arialbd.ttf", "arial.ttf", "segoeuib.ttf", "calibri.ttf"):
        path = os.path.join("C:/Windows/Fonts", font_name)
        if os.path.exists(path):
            safe = _get_safe_ffmpeg_path(path)
            return f":fontfile='{safe}'"
    return ""


def render_promo(
    clip_configs: list,
    output_path: str,
    hook_audio_path: str = None
) -> str:
    """
    Dedicated render pipeline for Promo videos (e.g., Acrylic OBS screen recordings).
    Reuses core encoder logic (ENCODE_FLAGS, _run_ffmpeg, _concat_with_xfade)
    to prevent code duplication and configuration drift.

    Features:
    1. Direct ingestion of local video clips (no stock b-roll fetching).
    2. Burns clean text overlays via FFmpeg drawtext (hooks carried visually).
    3. Muxes optional short spoken hook (3-5s) at the start while keeping the main body silent
       by default so native platform trending audio can be attached at upload time.
    4. Explicitly skips word-level SRT subtitle burn-in.

    clip_configs format:
    [
      {"path": "raw/obs/clip1.mp4", "overlay_text": "Hook text", "duration_seconds": 3.5},
      ...
    ]
    """
    temp_dir = config.VIDEO_TEMP_DIR
    os.makedirs(temp_dir, exist_ok=True)

    xfade_duration = 0.3
    clip_count = len(clip_configs)

    print(f"    [render_promo] Using {'GPU' if settings.ENCODER == 'h264_nvenc' else 'CPU'} encoder ({settings.ENCODER})")
    print("    [render_promo] Subtitles: Skipped by design (text overlays carry the message)")
    print("    Processing promo clips & overlays...")

    processed_clips = []
    font_param = _get_drawtext_font()

    for i, clip_info in enumerate(clip_configs):
        clip_path = clip_info.get("path")
        if not clip_path or not os.path.exists(clip_path) or os.path.getsize(clip_path) < 1024:
            print(f"    Warning: Skipping invalid or missing clip: {clip_path}")
            continue

        out = os.path.join(temp_dir, f"promo_processed_{i}.mp4")
        source_dur = _get_video_duration(clip_path)

        # Use configured duration if specified, else use natural clip duration
        target_dur = float(clip_info.get("duration_seconds", source_dur))
        target_dur = max(target_dur, 2.0)
        if clip_count > 1 and i < clip_count - 1:
            target_dur += xfade_duration

        loop_count = 0
        if source_dur > 0 and source_dur < target_dur:
            import math
            loop_count = math.ceil(target_dur / source_dur) - 1

        # Build video filter chain using Universal UI Fit + Glassmorphic Box-Blur Background
        # to ensure left/right sidebars and drawers are never sliced off by center cropping.
        vf_chain = (
            "split[bg][fg];"
            "[bg]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,boxblur=25:10,colorchannelmixer=rr=0.4:gg=0.4:bb=0.4[bg_out];"
            "[fg]scale=1080:1920:force_original_aspect_ratio=decrease[fg_out];"
            "[bg_out][fg_out]overlay=(W-w)/2:(H-h)/2,setsar=1"
        )

        overlay_text = clip_info.get("overlay_text", "").strip()
        if overlay_text:
            safe_text = _escape_drawtext_str(overlay_text)
            drawtext_filter = (
                f",drawtext=text='{safe_text}'{font_param}:"
                "fontsize=60:fontcolor=white:"
                "x=(w-text_w)/2:y=380:"
                "box=1:boxcolor=black@0.7:boxborderw=24:"
                "borderw=2:bordercolor=black"
            )
            vf_chain += drawtext_filter

        cmd = ["ffmpeg", "-y"]
        if loop_count > 0:
            cmd.extend(["-stream_loop", str(loop_count)])
        cmd.extend([
            "-i", clip_path,
            "-t", str(target_dur),
            "-vf", vf_chain,
            "-r", "30",
        ])
        cmd.extend(ENCODE_FLAGS)
        cmd.extend(["-an", out])

        _run_ffmpeg(cmd, f"processing promo clip {i+1} ({target_dur:.2f}s)")
        processed_clips.append(out)

    if len(processed_clips) < 1:
        raise RuntimeError("No promo clips were successfully processed.")

    # ── Step 2: Concatenate clips (with xfade if possible) ──
    concat_out = os.path.join(temp_dir, "promo_concatenated.mp4")
    if len(processed_clips) >= 2:
        print(f"    Concatenating promo clips with {xfade_duration}s cross-fade transitions...")
        concat_out = _concat_with_xfade(processed_clips, concat_out, xfade_duration)
    else:
        print("    Single clip, copying...")
        shutil.copy2(processed_clips[0], concat_out)

    visual_duration = _get_video_duration(concat_out)

    # ── Step 3: Add Spoken Hook (if provided) & Leave Main Body Silent ──
    # Note: We intentionally do NOT mix background music (BGM) here.
    # The promo video must remain silent by default for the main body so that
    # native platform trending audio can be cleanly attached at upload time
    # (avoiding copyright hits and preserving algorithmic discovery boosts).
    audio_mixed_out = os.path.join(temp_dir, "promo_with_audio.mp4")
    has_hook = hook_audio_path and os.path.exists(hook_audio_path) and os.path.getsize(hook_audio_path) > 0

    if has_hook:
        print(f"    Adding spoken hook ({hook_audio_path}) with silent padding for native upload BGM...")
        cmd = [
            "ffmpeg", "-y",
            "-i", concat_out,
            "-i", hook_audio_path,
            "-filter_complex", "[1:a]apad[out]",
            "-map", "0:v",
            "-map", "[out]",
            "-t", f"{visual_duration:.2f}",
            "-c:v", "copy",
            "-c:a", "aac",
            "-b:a", "192k",
            audio_mixed_out
        ]
        _run_ffmpeg(cmd, "adding hook audio")
    else:
        print("    No spoken hook provided — exporting silent video stream ready for native trending sound overlay.")
        shutil.copy2(concat_out, audio_mixed_out)

    # ── Step 4: Final export (No subtitle burn-in) ──
    print("    Final export for promo video...")
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

    cmd = [
        "ffmpeg", "-y",
        "-i", audio_mixed_out
    ]
    cmd.extend(FINAL_ENCODE_FLAGS)
    cmd.extend([
        "-c:a", "copy",
        "-pix_fmt", "yuv420p",
        "-movflags", "+faststart",
        output_path
    ])
    _run_ffmpeg(cmd, "promo final export")

    try:
        shutil.rmtree(temp_dir, ignore_errors=True)
    except OSError:
        pass

    print(f"  ✓ Promo Rendered: {output_path}")
    print("  ✓ Audio: Spoken hook only (main body silent for native platform trending music)")
    return output_path
