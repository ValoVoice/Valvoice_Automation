from google import genai
import json
import os
import settings
import config

client = genai.Client(api_key=settings.GEMINI_API_KEY)

# Niche-specific rules for maximum Information Gain score
# This is what beats YouTube's duplicate-detection algorithm
NICHE_INSTRUCTIONS = """
NICHE-SPECIFIC RULES for AI/ML/CS content:
- Lead with a counterintuitive fact that even CS students get wrong
- Use one concrete analogy that makes the abstract concept visual
- Include one specific number or benchmark (accuracy %, parameter count, year)
- End with "here's what this means practically" — one sentence only
- Avoid: "neural networks are like the brain", "AI is changing everything"
- Use instead: specific architecture names, paper titles, real benchmarks
"""

# ── Format Rotation (A/B/C) ──
# Rotating between structural formats prevents YouTube from detecting
# template uniformity — the #1 signal of mass-produced content.
FORMAT_COUNTER_FILE = config.FORMAT_COUNTER_FILE

FORMAT_TEMPLATES = {
    "A": """STRUCTURAL FORMAT: MYTH-BUST
- Open with a commonly held wrong belief about this topic
- Spend 35-40 seconds destroying it with specific evidence
- End with the correct understanding in one punchy sentence
- The viewer should feel "I was wrong, now I know"
""",
    "B": """STRUCTURAL FORMAT: HIDDEN INSIGHT
- Open with a surprising implication or side-effect of this topic
- Spend 35-40 seconds building understanding of WHY it matters
- End with one practical takeaway nobody else mentions
- The viewer should feel "I never thought about it that way"
""",
    "C": """STRUCTURAL FORMAT: SPECIFIC NUMBER
- Open with one precise data point that seems wrong or shocking
- Spend 35-40 seconds explaining why that number is real
- End with what this means for someone learning this topic
- The viewer should feel "that number changes everything"
""",
}

MAX_TOTAL_NARRATION_WORDS = 120
MAX_SCENE_NARRATION_WORDS = 22
MAX_SCRIPT_DURATION_SECONDS = 44


def _count_words(text: str) -> int:
    """Count spoken words using a conservative whitespace split."""
    return len(str(text).split())


def _script_validation_error(script: dict) -> str | None:
    """Return a validation error message if the script is too long."""
    scenes = script.get("scenes", [])
    if len(scenes) != 6:
        return f"expected exactly 6 scenes, got {len(scenes)}"

    total_words = 0
    total_duration = 0
    for scene in scenes:
        words = _count_words(scene.get("narration", ""))
        total_words += words
        total_duration += float(scene.get("duration_seconds", 0))
        if words > MAX_SCENE_NARRATION_WORDS:
            return (
                f"scene {scene.get('scene_number', '?')} has {words} words; "
                f"max is {MAX_SCENE_NARRATION_WORDS}"
            )
        if float(scene.get("duration_seconds", 0)) > 8:
            return f"scene {scene.get('scene_number', '?')} is over 8 seconds"

    if total_words > MAX_TOTAL_NARRATION_WORDS:
        return f"total narration has {total_words} words; max is {MAX_TOTAL_NARRATION_WORDS}"
    if total_duration > MAX_SCRIPT_DURATION_SECONDS:
        return f"script duration sum is {total_duration:g}s; max is {MAX_SCRIPT_DURATION_SECONDS}s"

    return None


def _get_next_format() -> str:
    """Rotate through A/B/C script formats to avoid template uniformity."""
    try:
        with open(FORMAT_COUNTER_FILE, "r") as f:
            data = json.load(f)
            last = data.get("last_format", "C")
    except (FileNotFoundError, json.JSONDecodeError):
        last = "C"

    rotation = {"A": "B", "B": "C", "C": "A"}
    next_format = rotation.get(last, "A")

    with open(FORMAT_COUNTER_FILE, "w") as f:
        json.dump({"last_format": next_format}, f)

    return next_format


def generate_script(topic: str) -> dict:
    """
    Calls Gemini to generate a structured JSON script
    optimized for YouTube Shorts retention.

    Uses format rotation (A/B/C) to avoid template uniformity.
    Includes an automatic fallback mechanism for models if the API key
    doesn't support the preferred model.

    Returns dict with: title, hook, scenes[], tags[], description
    """
    preferred_model = settings.SCRIPT_MODEL
    # Priority: SCRIPT_MODEL -> 3.5 Flash -> 2.5 Flash
    models_to_try = [preferred_model, "models/gemini-3.5-flash", "models/gemini-2.5-flash"]
    # Remove duplicates while preserving order
    models_to_try = list(dict.fromkeys(models_to_try))

    niche = settings.CHANNEL_NICHE

    # Get the next format in the A/B/C rotation
    script_format = _get_next_format()
    format_instructions = FORMAT_TEMPLATES[script_format]
    print(f"  ✓ Script format: {script_format} ({['Myth-bust', 'Hidden insight', 'Specific number'][['A','B','C'].index(script_format)]})")

    prompt = f"""
You are a viral YouTube Shorts scriptwriter specializing in {niche}.

Topic: {topic}

{format_instructions}

STRICT RULES:
- Hook in first 3 words. Start with a surprising fact or bold claim, NOT "Did you know"
- Total spoken duration: 40-50 seconds maximum (STRICT — must stay under 50s for YouTube Shorts)
- HARD WORD LIMIT: 120 spoken words total across all scenes
- HARD SCENE LIMIT: 22 spoken words maximum per scene
- Every sentence must earn its place. Cut anything that doesn't add new information
- No filler phrases: "In this video", "Let's dive in", "Stay tuned"
- End with one specific, actionable insight — not "follow for more"
- Information must be factually accurate and verifiable
- For 'visual_keywords', generate an array of EXACTLY TWO broad, 1-2 word conceptual keywords (e.g., ["server room", "cyber"], ["circuit board", "data center"]). Prefer 2-word phrases to avoid repetition. Never use long descriptive sentences.

{NICHE_INSTRUCTIONS}

Output ONLY valid JSON, no markdown, no explanation:
{{
  "title": "YouTube title with #Shorts, max 80 chars",
  "hook": "First sentence only, max 15 words",
  "format": "{script_format}",
  "scenes": [
    {{
      "scene_number": 1,
      "narration": "exact words to speak",
      "visual_keywords": ["1-2 word broad keyword", "another 1-2 word broad keyword"],
      "duration_seconds": 7
    }}
  ],
  "tags": ["tag1", "tag2", "tag3", "tag4", "tag5"],
  "description": "YouTube description, 150 chars max"
}}

Generate exactly 6 scenes. Each scene should be 5-8 seconds max. Total duration_seconds sum must be 44 seconds or less.
"""

    last_validation_error = None
    for attempt in range(3):
        attempt_prompt = prompt
        if last_validation_error:
            attempt_prompt += (
                "\n\nYour previous output was rejected because "
                f"{last_validation_error}. Regenerate from scratch with much shorter narration. "
                "Do not exceed 120 total spoken words."
            )

        response = None
        for current_model_name in models_to_try:
            try:
                model_id = current_model_name.replace("models/", "")
                response = client.models.generate_content(
                    model=model_id,
                    contents=attempt_prompt
                )
                break  # Success
            except Exception as e:
                # If it's a quota or access issue, it falls back
                print(f"  Warning: Model {current_model_name} failed, trying fallback...")
                continue
                
        if not response:
            raise RuntimeError("All Gemini fallback models failed. Check your API key and internet connection.")
            
        try:
            text = response.text.strip()
        except ValueError:
            # Sometimes safety filters block generation resulting in no text
            print(f"  Warning: Model returned empty response (possibly blocked by safety).")
            continue

        # Strip markdown fences if Gemini wraps the response
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]

        try:
            script = json.loads(text.strip())
            validation_error = _script_validation_error(script)
            if validation_error:
                if attempt < 2:
                    print(f"  Warning: Gemini script too long, retrying... ({validation_error})")
                    last_validation_error = validation_error
                    continue
                raise ValueError(f"Gemini returned an overlong script: {validation_error}")
            break
        except json.JSONDecodeError as e:
            if attempt < 2:
                print(f"  Warning: Gemini returned invalid JSON, retrying... ({e})")
                continue
            raise ValueError(f"Gemini returned invalid JSON after 3 attempts: {e}\nRaw output:\n{text}")

    # Basic validation
    if "scenes" not in script or len(script["scenes"]) == 0:
        raise ValueError("Gemini returned a script with no scenes")
    if "title" not in script:
        raise ValueError("Gemini returned a script with no title")

    return script


if __name__ == "__main__":
    result = generate_script("How transformers actually work in 60 seconds")
    print(json.dumps(result, indent=2))
