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
A local CLI tool that generates YouTube Shorts as MP4 files.
One person uses it. No servers. No cloud infra.

## Core Principles
- Simple over clever. Always.
- If a change adds a new dependency, justify it first.
- If a change adds more than 20 lines, question whether it's needed.
- Never suggest Docker, FastAPI, databases, or web UIs for this project.
- Never add logging frameworks — `print()` is enough.
- Never abstract something that only exists in one place.
- **Obsidian Graph:** Always maintain a connected Obsidian graph. Ensure every new markdown file links back to `[[README]]` or other relevant hub files so no nodes are left isolated.
- **Automatic Version Control (MANDATORY):** Whenever you complete a task, edit code, fix a bug, or update documentation, you MUST automatically execute a git commit and push (`git add .`, `git commit -m "<descriptive message>"`, and `git push`) before finishing your turn. Do NOT wait for the user to explicitly tell you to commit or push—auto-pushing is a mandatory requirement for any file modification.

## Before Starting Any Task
Read [[PROJECT_MAP]] first. Update the Status column and "What's Left" checklist after completing any change.

## Before Making Any Change, Ask:
1. Does this solve a problem that actually exists right now?
2. Does this add a dependency?
3. Does this make the first-time run harder?
If yes to 2 or 3 — stop and ask the user first.

## Current Phase
Phase 1 — get one video rendering end to end.
Do not implement Phase 2 or Phase 3 features until explicitly asked.

## Stack (Locked)
- Gemini API (`google-genai`) — script generation
- Chatterbox-TTS — voice, local, CUDA (replaces edge-tts entirely)
- Pexels API — b-roll
- FFmpeg — rendering
- `python-dotenv`, `requests` — only other deps allowed

## GPU Notes
- RTX 5060 (8GB) requires torch cu128 build — see install_chatterbox.ps1 for install order.
- Do not run `pip install chatterbox-tts` without cu128 torch pre-installed first.

## What To Never Do
- Do not add new pip packages without asking
- Do not refactor working code unprompted
- Do not implement features from future phases
- Do not add error handling for problems that haven't occurred yet
- Do not create new files without being asked

## Developer Workflows & State
- `.env` drives runtime config: `GEMINI_API_KEY`, `PEXELS_API_KEY`, etc.
- Keep `format_counter.json` and `used_clips.json` unless you want to reset rotation and dedup history.
- Script-only dry run (LLM JSON): `python main.py --script-only --topic "..."`.
- Full render: `python main.py --topic "..."`.
- Final artifacts live in `artifacts/output/`; temp assets are deleted after a successful render.

## Environment Hygiene
Before treating any file-count, graph structure, or "everything is 
clean now" claim as resolved, show the actual command output 
(file listing, node count, directory tree) — not a description 
of what should be true. This applies to vault/graph state the 
same way it applies to render outputs.

## Single Source of Truth
All project documentation lives as flat files directly inside 
Youtube Automation/. No subfolders like docs/, wiki/, or 
Decisions/ may be created. If new categories of information 
arise, they become a new section inside PROJECT_MAP.md or 
SESSION_LOG.md, never a new file or folder, unless the user 
explicitly asks for a new file by name.
