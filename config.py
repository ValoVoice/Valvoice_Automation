"""Central configuration for path constants used across the project.

Keep all mutable runtime paths here so the codebase can be reorganized
without scattering string literals across multiple files.

This module intentionally returns absolute paths so all callers can use
the same canonical paths on Windows and other platforms.
"""
from __future__ import annotations

import os
from pathlib import Path

# Base repository directory (absolute)
BASE_DIR = Path(__file__).resolve().parent

def _p(relative: str) -> str:
    """Return an absolute path for a file/directory inside the repo."""
    return str(BASE_DIR.joinpath(*relative.split("/")))

# Directories (absolute paths)
ARTIFACTS_DIR = _p("artifacts")
GENERATED_SCRIPTS_DIR = os.path.join(ARTIFACTS_DIR, "generated_scripts")
AUDIO_DIR = os.path.join(ARTIFACTS_DIR, "audio")
SUBTITLES_DIR = os.path.join(ARTIFACTS_DIR, "subtitles")
VIDEO_DIR = os.path.join(ARTIFACTS_DIR, "video")
VIDEO_ASSETS_DIR = os.path.join(VIDEO_DIR, "assets")
VIDEO_TEMP_DIR = os.path.join(VIDEO_DIR, "temp")
OUTPUT_DIR = os.path.join(ARTIFACTS_DIR, "output")
SONGS_DIR = _p("songs")

# Runtime state (kept separate from source)
STATE_DIR = _p("state")
FORMAT_COUNTER_FILE = os.path.join(STATE_DIR, "format_counter.json")
USED_CLIPS_FILE = os.path.join(STATE_DIR, "used_clips.json")

# Small helper: ensure the state dir exists when the module is imported
os.makedirs(STATE_DIR, exist_ok=True)

