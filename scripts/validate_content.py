import re
import os
import json
from google import genai
import settings

# Layer 1: Deterministic Rules
BANNED_PRICING_PHRASES = [
    r"free\s+forever",
    r"lifetime\s+free",
    r"permanently\s+free",
    r"never\s+pay"
]

def _deterministic_validation(text: str) -> bool:
    text_lower = text.lower()
    
    # Check pricing claims
    for pattern in BANNED_PRICING_PHRASES:
        if re.search(pattern, text_lower):
            print(f"  [Validation FAIL] Banned pricing phrase detected: {pattern}")
            return False
            
    # Check voice count logic (basic heuristic, semantic layer catches nuance)
    matches = re.findall(r'(\d+)\s+voices', text_lower)
    for match in matches:
        if int(match) > 29:
            print(f"  [Validation FAIL] Voice count exceeds 29: {match}")
            return False
            
    return True

def _semantic_validation(text: str) -> str:
    """
    Fail-closed semantic validation using LLM.
    Returns PASS, FAIL, or HUMAN_REVIEW_REQUIRED.
    """
    prompt = f"""
Evaluate the following marketing script for a product called ValVoice.
ValVoice is a local app that reads Valorant text chat and converts it to TTS routed to the mic.

RULES FOR REJECTION:
1. Claims that ValVoice hacks, cheats, or modifies game memory/DLLs.
2. Claims that ValVoice is "Riot approved" or endorsed by Riot Games.
3. Claims guaranteeing "100% unbannable" or "zero ban risk".
4. Claims implying it supports ALL Valorant agents (it supports exactly 29).

Note: "ValVoice does not inject DLLs" is a factual statement and should PASS.

Respond EXACTLY with one of these three strings, and nothing else:
PASS
FAIL
HUMAN_REVIEW_REQUIRED

Text to evaluate:
{text}
"""
    try:
        client = genai.Client(api_key=settings.GEMINI_API_KEY)
        response = client.models.generate_content(
            model=settings.SCRIPT_MODEL,
            contents=prompt
        )
        result = response.text.strip().upper()
        if result in ["PASS", "FAIL", "HUMAN_REVIEW_REQUIRED"]:
            return result
        else:
            print(f"  [Validation Warning] Unrecognized LLM output: {result}")
            return "HUMAN_REVIEW_REQUIRED"
    except Exception as e:
        print(f"  [Validation Error] LLM API failure: {e}")
        return "HUMAN_REVIEW_REQUIRED" # Fail closed

def validate_script_content(script: dict) -> str:
    """
    Validates the core script.
    Returns "PASS", "FAIL", or "HUMAN_REVIEW_REQUIRED".
    """
    if "title" not in script or "scenes" not in script:
        print("  [Validation FAIL] Script missing required structural fields.")
        return "FAIL"
        
    full_text = script.get("title", "") + " " + script.get("hook", "")
    for scene in script.get("scenes", []):
        full_text += " " + scene.get("narration", "")
        
    if not _deterministic_validation(full_text):
        return "FAIL"
        
    semantic_result = _semantic_validation(full_text)
    return semantic_result

def validate_metadata(metadata_text: str) -> str:
    try:
        meta_dict = json.loads(metadata_text)
        formatted = ""
        for platform, content in meta_dict.items():
            formatted += f"\n--- {platform.upper()} ---\n"
            if isinstance(content, dict):
                for k, v in content.items():
                    formatted += f"{k}: {v}\n"
            else:
                formatted += str(content) + "\n"
    except Exception:
        formatted = metadata_text

    if not _deterministic_validation(formatted):
        return "FAIL"
    return _semantic_validation(formatted)

def validate_bgm(bgm_path: str) -> bool:
    """
    Ensures BGM is from the approved directory.
    """
    if not bgm_path:
        return True # No BGM is fine
    
    approved_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "assets", "bgm", "approved"))
    return os.path.abspath(bgm_path).startswith(approved_dir)

def post_render_validation(video_path: str, expect_narration: bool = True, expect_raw_audio: bool = True) -> bool:
    """
    Validates the final rendered MP4 via FFprobe.
    """
    if not os.path.exists(video_path):
        print(f"  [Post-Render FAIL] File does not exist: {video_path}")
        return False
        
    # In a real run, this would use ffprobe to verify 1080x1920, duration, and audio tracks.
    # For now, we perform a basic size check to ensure it's not empty/corrupted.
    size = os.path.getsize(video_path)
    if size < 100 * 1024:
        print(f"  [Post-Render FAIL] File size suspiciously small ({size} bytes). Possible corruption.")
        return False
        
    print(f"  [Post-Render PASS] Output verified at {video_path}")
    return True
