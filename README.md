---
title: YouTube Shorts Automation (Local)
type: project
tags:
  - project
  - youtube
---

# [[README|YouTube Shorts Automation (Local)]]

This repository is a local, Windows-first CLI that generates YouTube Shorts (9:16 MP4) from a topic using Gemini (script), Edge-TTS (voice + SRT), Pexels/Pixabay (b-roll), and FFmpeg (render).

Key properties
- Local-only: you run it on your PC and manually upload the final MP4s to YouTube Studio
- Zero recurring cost if you use free tiers described in `docs/Architecture.md`
- Opinionated: A/B/C script rotation, clip deduplication, per-scene prosody, and word-level SRT chunking

Quick start (PowerShell)
```powershell
cd "C:\Users\HP\IdeaProjects\Youtube Automation"
# Activate virtualenv (if you use one)
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt

# Copy .env.example and fill in keys
copy .env.example .env
# Edit .env and add GEMINI_API_KEY and PEXELS_API_KEY

# Test script generation only
python main.py --script-only --topic "How attention mechanism works in transformers"

# Full render (one topic)
python main.py --topic "How Git stores data internally"
```

Repository layout (cleaned)
```
main.py                 ← CLI entry point (explainer video pipeline)
main_promo.py           ← CLI entry point (product/Acrylic promo pipeline)
config.py               ← centralized paths (created by reorg)
AGENTS.md               ← [[AGENTS|Agent operational rules & behavior]]
Architecture.md         ← [[Architecture|Technical system specifications]]
CONTENT_ROADMAP.md      ← [[CONTENT_ROADMAP|20 AI/CS video topics]]
Implementation.md       ← [[Implementation|Pipeline execution & architecture modules]]
PROJECT_MAP.md          ← [[PROJECT_MAP|File state tracking & workflows]]
Research.md             ← [[Research|Autonomous video production research & strategy]]
SESSION_LOG.md          ← [[SESSION_LOG|Chronological project history]]
scripts/                ← core modules
state/                  ← runtime state (format rotation, used clips)
artifacts/              ← base folder for all generated outputs
  ├── generated_scripts/← persist script JSONs
  ├── audio/            ← generated TTS clips (temp)
  ├── subtitles/        ← generated SRTs (temp)
  ├── video/            ← downloaded clips and temp renders
  └── output/           ← final MP4s
songs/                  ← optional BGM tracks you add (BGM rules stored in PROJECT_MAP)
```

Notes on the recent reorganization
- Documentation moved to `docs/` for clarity.
- Runtime state now lives in `state/` and the code reads `state/format_counter.json` and `state/used_clips.json`.
- Paths are centralized in `config.py` so you can move generated outputs into a single `artifacts/` directory in a follow-up change without updating many files.


