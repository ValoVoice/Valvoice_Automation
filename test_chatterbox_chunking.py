import asyncio
import os
import sys

# Ensure we can import from scripts
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from scripts.generate_audio import generate_audio_for_scenes

async def main():
    test_scene = {
        "narration": "This is a long paragraph meant to simulate a full explainer scene with multiple sentences strung together to see if the chunking correctly splits and reassembles the audio without truncation or garbage output at the boundary."
    }
    os.makedirs("artifacts/audio", exist_ok=True)
    
    print("Testing Chatterbox TTS chunking...")
    await generate_audio_for_scenes(
        scenes=[test_scene], 
        output_path="artifacts/audio/chunk_test.mp3", 
        srt_path=None
    )
    print("Done. Listen to artifacts/audio/chunk_test.mp3")

if __name__ == "__main__":
    asyncio.run(main())
