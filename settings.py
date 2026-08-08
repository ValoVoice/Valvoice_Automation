"""Central settings module for environment variables and API keys.

This loads the `.env` file and provides typed access with defaults
to configuration parameters used across the project.
"""
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# API Keys
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
PEXELS_API_KEY = os.getenv("PEXELS_API_KEY", "")
PIXABAY_API_KEY = os.getenv("PIXABAY_API_KEY", "")

if not GEMINI_API_KEY:
    raise EnvironmentError("GEMINI_API_KEY is missing from environment variables or .env file.")
if not PEXELS_API_KEY:
    raise EnvironmentError("PEXELS_API_KEY is missing from environment variables or .env file.")

# Preferences
CHANNEL_NICHE = os.getenv("CHANNEL_NICHE", "technology")
SCRIPT_MODEL = os.getenv("SCRIPT_MODEL", "models/gemini-3.1-pro-preview")

# Chatterbox TTS Settings
EXAGGERATION_EXPLAINER = float(os.getenv("EXAGGERATION_EXPLAINER", "0.35"))
EXAGGERATION_PROMO_HOOK = float(os.getenv("EXAGGERATION_PROMO_HOOK", "0.7"))
CFG_WEIGHT = float(os.getenv("CFG_WEIGHT", "0.5"))

# Feature Flags / Constants
# If a scene is longer than this duration, it will be split visually (Phase 3 A/B splitting)
MAX_SCENE_DURATION_BEFORE_SPLIT = 4.0
VISUAL_SUFFIXES = [" visualization", " data", " network", " code", " technology"]

import subprocess

def get_video_encoder() -> str:
    """Returns h264_nvenc if available, falls back to libx264."""
    try:
        result = subprocess.run(
            ["ffmpeg", "-hide_banner", "-encoders"],
            capture_output=True, text=True
        )
        if "h264_nvenc" in result.stdout:
            return "h264_nvenc"
    except Exception:
        pass
    return "libx264"

ENCODER = get_video_encoder()
