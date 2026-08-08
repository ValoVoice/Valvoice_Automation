---
title: Agents
type: concept
tags:
  - concept
  - agents
---

# [[AGENTS]]

*Return to [[README]]*

## What This Project Is
A local CLI tool that generates multi-platform (YouTube, Instagram, Reddit, Hacker News) content for **ValVoice** using raw, real product assets.
This is a **Raw-Asset-First** content engine. It does not recreate ValVoice XTTS capabilities or rely on generic stock footage.

## Core Principles
- **Simple over clever. Always.**
- **No AI Voice Hallucinations:** We use Edge-TTS for narrator voice-overs. The actual ValVoice/XTTS audio comes strictly from the raw input footage. Do not build XTTS models here.
- **Strict Content Validation:** Content must pass concrete (Layer 1) and Fail-Closed Semantic (Layer 2) validations.
- **Traceability:** Every generated output has a frontmatter in Obsidian tracking its generation model, prompt version, and validation state.
- **Human Review Gate:** No automatic publishing. Content enters `pending-review` in Obsidian.
- **Automatic Version Control (MANDATORY):** Auto-commit and push to GitHub regularly after phase completion.

## Current Phase Roadmap
We are executing the 11-Phase ValVoice Automation Pivot. See task tracking for progress.

## Stack (Locked)
- Gemini API (`google-genai`) — script and metadata generation, semantic validation
- Edge-TTS — narrator voice
- FFmpeg — rendering and dual-audio mixing
- Local Asset Selection (`select_assets.py`) — mapping required tags to raw user-provided assets
- `python-dotenv`, `requests` — only other dependencies allowed

## Developer Workflows & State
- `.env` drives runtime config: `GEMINI_API_KEY`, etc.
- `format_counter.json` tracks the 10-pillar rotation.
- Scripts evaluate using atomic Pre-Render, Metadata, and Post-Render validation gates.
- Output artifacts track traceability and await Human Review.
- All product knowledge lives in `ValVoice/Product/` (Obsidian).
