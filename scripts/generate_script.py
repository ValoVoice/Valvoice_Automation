from google import genai
import json
import os
import settings
import config

client = genai.Client(api_key=settings.GEMINI_API_KEY)

# 10 Pillar Rotation
FORMAT_COUNTER_FILE = config.FORMAT_COUNTER_FILE

PILLARS = {
    "1": "PRODUCT DEMO",
    "2": "FEATURE SHOWCASE",
    "3": "FUN / VIRAL",
    "4": "VALORANT SCENARIO",
    "5": "AI / TECHNOLOGY",
    "6": "DEVELOPMENT / BUILD IN PUBLIC",
    "7": "EARLY ACCESS",
    "8": "TUTORIAL",
    "9": "RELEASE / UPDATE",
    "10": "COMMUNITY"
}

def _get_next_pillar() -> str:
    try:
        with open(FORMAT_COUNTER_FILE, "r") as f:
            data = json.load(f)
            last = str(data.get("last_pillar", "10"))
    except (FileNotFoundError, json.JSONDecodeError):
        last = "10"
    
    next_num = str(int(last) + 1) if int(last) < 10 else "1"
    
    with open(FORMAT_COUNTER_FILE, "w") as f:
        json.dump({"last_pillar": next_num}, f)
        
    return PILLARS.get(next_num, "PRODUCT DEMO")

MAX_TOTAL_NARRATION_WORDS = 120
MAX_SCENE_NARRATION_WORDS = 22
MAX_SCRIPT_DURATION_SECONDS = 44

def _count_words(text: str) -> int:
    return len(str(text).split())

def _script_validation_error(script: dict) -> str | None:
    scenes = script.get("scenes", [])
    if not scenes:
        return "no scenes found"
        
    total_words = 0
    total_duration = 0
    for scene in scenes:
        words = _count_words(scene.get("narration", ""))
        total_words += words
        total_duration += float(scene.get("duration_seconds", 0))
        if words > MAX_SCENE_NARRATION_WORDS:
            return f"scene {scene.get('scene_number', '?')} has {words} words; max is {MAX_SCENE_NARRATION_WORDS}"
            
    if total_words > MAX_TOTAL_NARRATION_WORDS:
        return f"total narration has {total_words} words; max is {MAX_TOTAL_NARRATION_WORDS}"
        
    return None

def generate_script(topic: str) -> dict:
    preferred_model = settings.SCRIPT_MODEL
    models_to_try = [preferred_model, "models/gemini-3.5-flash", "models/gemini-2.5-flash"]
    models_to_try = list(dict.fromkeys(models_to_try))

    pillar = _get_next_pillar()
    print(f"  ✓ Content Pillar: {pillar}")

    prompt = f"""
You are a content strategist for ValVoice, a Windows desktop app that converts Valorant text chat into AI speech and routes it to voice chat.
Topic: {topic}
Content Pillar: {pillar}

VALVOICE PRODUCT ACCURACY:
- ValVoice has EXACTLY 29 voices. Never claim more.
- Pricing: "Full Premium Access — FREE during Early Access." Never use "free forever" or "lifetime free".
- Do not claim Riot Games endorsement, approval, or "zero ban risk".
- Focus on real features: OCR chat reading, AI voice generation, Push-to-Talk integration, virtual audio routing.

SCRIPT RULES:
- Hook in the first 3 words.
- Max 120 words total narration. Max 22 words per scene.
- Keep it punchy and engaging.

ASSET RULES:
For each scene, provide 'required_visuals' as an array of tags mapping to real raw assets.
Valid tags are ONLY: "valvoice_demo", "gameplay", "screenshot", "ui".
DO NOT invent other tags.

Output ONLY valid JSON:
{{
  "title": "Title max 80 chars",
  "hook": "First sentence hook",
  "pillar": "{pillar}",
  "scenes": [
    {{
      "scene_number": 1,
      "narration": "exact words for Edge-TTS narrator to speak",
      "required_visuals": ["valvoice_demo"],
      "duration_seconds": 6
    }}
  ]
}}
"""

    last_validation_error = None
    for attempt in range(3):
        attempt_prompt = prompt
        if last_validation_error:
            attempt_prompt += f"\nFix this error: {last_validation_error}. Keep it shorter."

        response = None
        for current_model_name in models_to_try:
            try:
                model_id = current_model_name.replace("models/", "")
                response = client.models.generate_content(model=model_id, contents=attempt_prompt)
                break
            except Exception as e:
                continue
                
        if not response:
            raise RuntimeError("All Gemini models failed.")
            
        try:
            text = response.text.strip()
        except ValueError:
            continue

        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]

        try:
            script = json.loads(text.strip())
            validation_error = _script_validation_error(script)
            if validation_error:
                if attempt < 2:
                    last_validation_error = validation_error
                    continue
                raise ValueError(f"Script too long: {validation_error}")
            break
        except json.JSONDecodeError as e:
            if attempt < 2:
                continue
            raise ValueError(f"Invalid JSON: {{e}}")

    return script
