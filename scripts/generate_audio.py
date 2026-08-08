import asyncio
import os
import subprocess
import torch
import soundfile as sf
import re
import numpy as np
from chatterbox.tts import ChatterboxTTS

import settings

# Lazy load model
_model = None

def get_model():
    """Lazy-load model once, reuse across calls in same session."""
    global _model
    if _model is None:
        if not torch.cuda.is_available():
            raise RuntimeError(
                "CUDA not available — Chatterbox will be extremely slow on CPU. "
                "Check your torch install before proceeding."
            )
        print("    [audio] Loading ChatterboxTTS model to CUDA...")
        _model = ChatterboxTTS.from_pretrained(device="cuda")
    return _model

def _get_audio_duration_ms(audio_path: str) -> int:
    """Get audio duration in milliseconds. Tries ffprobe, then ffmpeg, then estimates."""
    import re
    # Try 1: ffprobe
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", audio_path],
            capture_output=True, text=True, check=True
        )
        seconds = float(result.stdout.strip())
        return int(seconds * 1000)
    except (subprocess.CalledProcessError, ValueError, FileNotFoundError):
        pass

    # Try 2: ffmpeg -i
    try:
        result = subprocess.run(
            ["ffmpeg", "-i", audio_path, "-hide_banner"],
            capture_output=True, text=True
        )
        match = re.search(r"Duration:\s*(\d+):(\d+):(\d+)\.(\d+)", result.stderr)
        if match:
            h, m, s, cs = int(match.group(1)), int(match.group(2)), int(match.group(3)), int(match.group(4))
            seconds = h * 3600 + m * 60 + s + cs / 100.0
            return int(seconds * 1000)
    except (FileNotFoundError, OSError):
        pass

    return 8000

def chunk_narration(text: str, max_words: int = 25) -> list[str]:
    sentences = re.split(r'(?<=[.?!])\s+', text.strip())
    chunks = []
    for sentence in sentences:
        words = sentence.split()
        if len(words) <= max_words:
            chunks.append(sentence)
        else:
            # Further split oversized sentences by clause
            for i in range(0, len(words), max_words):
                chunks.append(" ".join(words[i:i + max_words]))
    return [c for c in chunks if c.strip()]

async def generate_audio_for_scenes(scenes: list, output_path: str, srt_path: str,
                                     voice: str = None) -> dict:
    """
    Generates audio for all scenes using Chatterbox-TTS.
    Subtitles (SRT) are no longer generated for Chatterbox.
    """
    temp_segments = []
    scene_duration_ms_list = []

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    if srt_path:
        os.makedirs(os.path.dirname(srt_path) or ".", exist_ok=True)
        # Create an empty SRT file to avoid breaking downstream tasks that check for it
        with open(srt_path, "w", encoding="utf-8") as f:
            pass

    model = get_model()
    exag = settings.EXAGGERATION_EXPLAINER
    cfg = settings.CFG_WEIGHT

    for i, scene in enumerate(scenes):
        narration = scene["narration"]
        segment_path = output_path + f".scene_{i}.wav"
        temp_segments.append(segment_path)

        # Generate each scene chunk by chunk
        chunks = chunk_narration(narration)
        chunk_wavs = []
        for chunk in chunks:
            wav = model.generate(chunk, exaggeration=exag, cfg_weight=cfg)
            chunk_wavs.append(wav.squeeze().cpu().numpy())
        
        if chunk_wavs:
            final_scene_wav = np.concatenate(chunk_wavs)
        else:
            final_scene_wav = np.zeros(model.sr, dtype=np.float32)
            
        sf.write(segment_path, final_scene_wav, model.sr)

        # Measure duration
        scene_duration_ms = _get_audio_duration_ms(segment_path)
        scene_duration_ms_list.append(scene_duration_ms)

    # Concatenate all scene audio segments into one file
    list_file = output_path + ".filelist.txt"

    with open(list_file, "w") as f:
        for seg in temp_segments:
            safe_path = os.path.abspath(seg).replace("\\", "/")
            f.write(f"file '{safe_path}'\n")

    # Concatenate and convert to mp3 (output_path should be mp3)
    # Add volume normalization if desired, here just simple concat to MP3
    concat_cmd = [
        "ffmpeg", "-y", "-f", "concat", "-safe", "0",
        "-i", list_file,
        "-af", "loudnorm=I=-16:TP=-1.5:LRA=11",
        "-c:a", "libmp3lame",
        output_path
    ]
    subprocess.run(concat_cmd, check=True)

    # Cleanup temp files
    for seg in temp_segments:
        if os.path.exists(seg):
            os.remove(seg)
    if os.path.exists(list_file):
        os.remove(list_file)

    final_audio_duration_ms = _get_audio_duration_ms(output_path)

    print(f"  Audio: {output_path} (Chatterbox-TTS)")
    print(f"  Subtitles: Skipped (Not generated for Chatterbox)")
    print(f"  Voice: Chatterbox Default (Exag: {exag}, CFG: {cfg})")
    print(f"  Normalized to -16 LUFS")

    return {
        "scene_durations": [ms / 1000 for ms in scene_duration_ms_list],
        "audio_duration": final_audio_duration_ms / 1000,
        "subtitle_chunks": 0,
    }

async def generate_audio(text: str, output_path: str, srt_path: str = None,
                         voice: str = None, exaggeration: float = None) -> None:
    """Legacy single-block audio generation."""
    model = get_model()
    
    if srt_path:
        os.makedirs(os.path.dirname(srt_path) or ".", exist_ok=True)
        with open(srt_path, "w", encoding="utf-8") as f:
            pass

    exag = exaggeration if exaggeration is not None else settings.EXAGGERATION_PROMO_HOOK
    wav = model.generate(text, exaggeration=exag, cfg_weight=settings.CFG_WEIGHT)
    
    # Save temp wav
    temp_wav = output_path + ".temp.wav"
    sf.write(temp_wav, wav.squeeze().cpu().numpy(), model.sr)
    
    # Convert and normalize
    cmd = [
        "ffmpeg", "-y",
        "-i", temp_wav,
        "-af", "loudnorm=I=-16:TP=-1.5:LRA=11",
        "-c:a", "libmp3lame",
        output_path
    ]
    try:
        subprocess.run(cmd, check=True)
    finally:
        if os.path.exists(temp_wav):
            os.remove(temp_wav)

    print(f"  Audio: {output_path}")

def build_full_narration(scenes: list) -> str:
    """Joins all scene narrations into a single text block for TTS."""
    return " ".join([scene["narration"] for scene in scenes])

if __name__ == "__main__":
    test_text = (
        "Testing one two three. Chatterbox is online."
    )
    os.makedirs("audio", exist_ok=True)
    asyncio.run(generate_audio(
        text=test_text,
        output_path="audio/isolated_test.mp3"
    ))
