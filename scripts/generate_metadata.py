import json
from google import genai
import settings

RIOT_DISCLAIMER = "\n\nNot affiliated with or endorsed by Riot Games. Valorant is a trademark of Riot Games, Inc."

def generate_platform_metadata(script: dict) -> dict:
    """
    Generates tailored platform metadata (YouTube, Instagram, Reddit, HackerNews)
    based on the master script. Automatically appends Riot disclaimer.
    """
    client = genai.Client(api_key=settings.GEMINI_API_KEY)
    
    script_text = json.dumps(script, indent=2)
    
    prompt = f"""
You are the developer of ValVoice, a local Windows app that routes AI TTS from Valorant text chat to the voice mic.
Generate cross-platform marketing metadata for this master script:
{script_text}

Rules:
- YouTube: Engaging Shorts description and tags.
- Instagram: Reel caption with fast pacing, emojis, and hashtags.
- Reddit: Authentic developer first-person post (e.g. "I built a tool..."). Do NOT use ad copy.
- HackerNews: Show HN post focusing on technical architecture (OCR, Audio routing, AI pipeline). No marketing fluff.

Output EXACTLY this JSON structure:
{{
  "youtube": {{
    "title": "",
    "description": "",
    "tags": []
  }},
  "instagram": {{
    "caption": ""
  }},
  "reddit": {{
    "title": "",
    "body": ""
  }},
  "hackernews": {{
    "title": "Show HN: ...",
    "body": ""
  }}
}}
"""

    response = client.models.generate_content(
        model=settings.SCRIPT_MODEL,
        contents=prompt
    )
    
    text = response.text.strip()
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
            
    try:
        metadata = json.loads(text.strip())
    except json.JSONDecodeError as e:
        raise ValueError(f"Failed to parse metadata JSON: {e}\nRaw output: {text}")
        
    # Automatically append Riot disclaimer to platforms that need it
    if "youtube" in metadata and "description" in metadata["youtube"]:
        metadata["youtube"]["description"] += RIOT_DISCLAIMER
    if "instagram" in metadata and "caption" in metadata["instagram"]:
        metadata["instagram"]["caption"] += RIOT_DISCLAIMER
    if "reddit" in metadata and "body" in metadata["reddit"]:
        metadata["reddit"]["body"] += RIOT_DISCLAIMER
        
    return metadata
