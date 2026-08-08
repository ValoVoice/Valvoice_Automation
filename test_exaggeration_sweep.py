import asyncio
import os
import sys

# Ensure we can import from scripts
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from scripts.generate_audio import generate_audio

async def main():
    test_text = "Solid state drives don't fail the way you think they do. Every single write operation slowly wears down the memory cells until they simply stop holding a charge."
    
    os.makedirs("artifacts/audio", exist_ok=True)
    
    for exag in [0.3, 0.4, 0.5]:
        await generate_audio(
            test_text,
            f"artifacts/audio/sweep_exag_{exag}.mp3",
            exaggeration=exag
        )
        print(f"Generated: sweep_exag_{exag}.mp3")

if __name__ == "__main__":
    asyncio.run(main())
