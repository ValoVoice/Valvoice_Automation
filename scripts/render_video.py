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
    try:
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as e:
        print(f"  ERROR: FFmpeg failed at: {step_name}")
        print(f"    stderr: {e.stderr[-500:] if e.stderr else 'no output'}")
        raise RuntimeError(f"FFmpeg error during {step_name}") from e

def _get_safe_ffmpeg_path(path: str) -> str:
    abs_path = os.path.abspath(path)
    safe = abs_path.replace("\\", "/")
    if len(safe) >= 2 and safe[1] == ":":
        safe = safe[0] + "\\:" + safe[2:]
    return safe

def _has_audio(path: str) -> bool:
    try:
        res = subprocess.run(["ffprobe", "-i", path, "-show_streams", "-select_streams", "a", "-loglevel", "error"], capture_output=True, text=True)
        return "codec_type" in res.stdout
    except:
        return False

def _get_video_duration(path: str) -> float:
    import re
    try:
        res = subprocess.run(["ffprobe", "-v", "quiet", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", path], capture_output=True, text=True, check=True)
        return float(res.stdout.strip())
    except:
        return 4.0

def render_short(scene_paths: list, scene_durations: list, audio_path: str, srt_path: str, output_path: str, bgm_track: str = None) -> str:
    """
    Renders the short by mixing raw video audio (preserving XTTS demos),
    Edge-TTS narration, and BGM, followed by subtitle burn-in.
    """
    temp_dir = config.VIDEO_TEMP_DIR
    os.makedirs(temp_dir, exist_ok=True)
    audio_duration = _get_video_duration(audio_path)
    
    print("    Processing clips (preserving raw audio)...")
    processed_clips = []
    
    for i, (clip_path, target_dur) in enumerate(zip(scene_paths, scene_durations)):
        if not os.path.exists(clip_path): continue
        out = os.path.join(temp_dir, f"proc_{i}.mp4")
        target_dur = max(float(target_dur), 2.0)
        
        has_a = _has_audio(clip_path)
        cmd = ["ffmpeg", "-y", "-i", clip_path]
        if not has_a:
            cmd.extend(["-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=44100"])
            
        cmd.extend([
            "-t", str(target_dur),
            "-vf", "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,setsar=1",
            "-r", "30"
        ])
        if not has_a:
            cmd.extend(["-map", "0:v", "-map", "1:a"])
        else:
            cmd.extend(["-map", "0:v", "-map", "0:a"])
            
        cmd.extend(ENCODE_FLAGS)
        cmd.extend(["-c:a", "aac", "-b:a", "192k", "-ar", "44100", "-ac", "2", out])
        _run_ffmpeg(cmd, f"processing clip {i}")
        processed_clips.append(out)

    concat_out = os.path.join(temp_dir, "concat.mp4")
    concat_list = os.path.join(temp_dir, "concat.txt")
    with open(concat_list, "w") as f:
        for c in processed_clips:
            f.write(f"file '{os.path.abspath(c).replace(chr(92), '/')}'\n")
            
    _run_ffmpeg(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", concat_list, "-c", "copy", concat_out], "concat")

    mix_out = os.path.join(temp_dir, "mix.mp4")
    
    print("    Mixing Edge-TTS, Raw Audio, and BGM...")
    cmd = ["ffmpeg", "-y", "-i", concat_out, "-i", audio_path]
    filter_complex = "[0:a]volume=1.0[a0];[1:a]volume=1.5[a1];"
    if bgm_track:
        cmd.extend(["-i", bgm_track])
        filter_complex += f"[2:a]volume=0.1,aloop=loop=-1:size=2e+09[a2];[a0][a1][a2]amix=inputs=3:duration=first:dropout_transition=2[aout]"
    else:
        filter_complex += f"[a0][a1]amix=inputs=2:duration=first:dropout_transition=2[aout]"
        
    cmd.extend([
        "-filter_complex", filter_complex,
        "-map", "0:v", "-map", "[aout]",
        "-c:v", "copy", "-c:a", "aac", "-b:a", "192k"
    ])
    if audio_duration > 0:
        cmd.extend(["-t", str(audio_duration)])
    cmd.append(mix_out)
    _run_ffmpeg(cmd, "audio mix")

    print("    Burning subtitles...")
    cmd = ["ffmpeg", "-y", "-i", mix_out]
    if srt_path and os.path.exists(srt_path):
        safe_srt = _get_safe_ffmpeg_path(srt_path)
        cmd.extend(["-vf", f"subtitles='{safe_srt}':force_style='FontName=Arial,FontSize=14,PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,Outline=2,Bold=1,Alignment=2,MarginV=80'"])
    cmd.extend(FINAL_ENCODE_FLAGS)
    cmd.extend(["-c:a", "copy", "-pix_fmt", "yuv420p", "-movflags", "+faststart", output_path])
    _run_ffmpeg(cmd, "final export")

    shutil.rmtree(temp_dir, ignore_errors=True)
    return output_path
