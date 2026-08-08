import asyncio
import os
import subprocess
import edge_tts
import settings

async def _get_audio_duration_ms(audio_path: str) -> int:
    try:
        proc = await asyncio.create_subprocess_exec(
            "ffprobe", "-v", "quiet", "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1", audio_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, _ = await proc.communicate()
        return int(float(stdout.strip()) * 1000)
    except:
        return 8000

async def generate_audio_for_scenes(scenes: list, output_path: str, srt_path: str, voice: str = None) -> dict:
    """
    Generates narration audio and subtitles using Edge-TTS.
    """
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    if srt_path:
        os.makedirs(os.path.dirname(srt_path) or ".", exist_ok=True)
        
    full_narration = " ".join([scene["narration"] for scene in scenes])
    
    # Use the voice specified in settings, or fallback to a standard narrator
    v = getattr(settings, 'EDGE_TTS_VOICE', "en-US-ChristopherNeural")
    
    communicate = edge_tts.Communicate(full_narration, v)
    submaker = edge_tts.SubMaker()
    
    with open(output_path, "wb") as f:
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                f.write(chunk["data"])
            elif chunk["type"] == "WordBoundary":
                submaker.create_sub((chunk["offset"], chunk["duration"]), chunk["text"])
                
    if srt_path:
        with open(srt_path, "w", encoding="utf-8") as f:
            f.write(submaker.generate_subs())
            
    duration_ms = await _get_audio_duration_ms(output_path)
    duration_s = duration_ms / 1000.0
    
    # Since we generate one continuous track, distribute durations evenly 
    # or proportionally to scene word count.
    total_words = sum(len(s["narration"].split()) for s in scenes)
    scene_durations = []
    
    for scene in scenes:
        words = len(scene["narration"].split())
        ratio = words / max(total_words, 1)
        scene_durations.append(max(duration_s * ratio, 2.0))
        
    return {
        "scene_durations": scene_durations,
        "audio_duration": duration_s
    }
