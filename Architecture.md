---
title: Architecture
type: concept
tags:
  - concept
  - architecture
---

# [[Architecture]]

This file describes the system architecture. See [[README]] for the quickstart.

---

## Code Overview

- **`settings.py`** — Loads `.env` variables and provides typed defaults for the project.
- **`config.py`** — Central path constants for the `artifacts/` directories.
- **`main.py`** — The entry point. Wires everything together, handles Phase 3 A/B visual splitting, and cleans up temp files.
- **`scripts/generate_script.py`** — Calls Gemini.

## Workflow (Your Daily Routine)

1. **Add topics** to `topics.txt` whenever inspiration strikes
2. **Run the script** — `python main.py --topics-file topics.txt --count 3`
3. **Open `artifacts/output/` folder** — watch the generated MP4s
4. **Delete bad ones**, keep the good ones
5. **Upload good ones manually** to YouTube via YouTube Studio
6. **Follow the upload checklist** (see below)
7. **Track what performs well**, add similar topics to `topics.txt`

Time investment: ~15 minutes per day.

---

## Upload Checklist (Every Single Video)

> **This is mandatory. YouTube's July 2025 "inauthentic content" policy is actively enforced.**

1. ☐ Watch the first 10 and last 10 seconds for audio/video sync
2. ☐ Review and fix the title — your single biggest SEO lever
3. ☐ Set category to **28 (Science & Technology)**
4. ☐ **Enable "Altered or synthetic content" label** — every video, no exceptions
5. ☐ Schedule for **Tue/Thu/Sat at 11am IST** — never 2 videos within 8 hours
6. ☐ Add description with keywords
7. ☐ Start with **Private** uploads for first 20 videos — review quality first

---

## Available Voices (Edge-TTS)

Pick one that sounds unique. Avoid `en-US-AvaNeural` — every automation channel uses it.

| Voice ID | Description |
| --- | --- |
| `en-GB-RyanNeural` | British male, distinctive **(default, recommended)** |
| `en-US-ChristopherNeural` | Male, professional |
| `en-AU-WilliamNeural` | Australian male, unique |
| `en-US-JennyNeural` | Female, warm |
| `en-US-AriaNeural` | Female, expressive |

Change the voice in your `.env` file: `VOICE=en-GB-RyanNeural`

---

## Gemini Model Options

| Model | Cost | Quality | When to Use |
| --- | --- | --- | --- |
| `gemini-2.5-flash` | Free (1,500 req/day) | Good | Default — daily video generation |
| `gemini-2.5-pro` | ~₹0.05/script (needs billing) | Excellent | Important topics, better narrative arcs |

Change the model in your `.env` file: `SCRIPT_MODEL=gemini-2.5-flash`

> **Note:** `gemini-2.0-flash` was shut down on June 1, 2026. Do NOT use it.

---

## Anti-Template Features

The pipeline has six systems to prevent YouTube from detecting mass-production patterns:

1. **A/B/C Format Rotation** — Every script follows one of three structural formats (myth-bust, hidden insight, specific number). Rotates automatically via `format_counter.json`

2. **Clip Deduplication** — Every Pexels + Pixabay clip ID is logged in `used_clips.json`. The same stock footage never appears in two videos

3. **Per-Scene Prosody Variation** — Each scene gets a slightly different speaking rate (+10% to +18%) and pitch (-2Hz to +2Hz), breaking the flat TTS monotone

4. **Background Music** — Random royalty-free track from `songs/` folder, mixed at -20dB under voiceover. Adds production value and unique audio fingerprint per video

5. **xfade Transitions** — 0.3s cross-fade between clips instead of jarring hard cuts. Falls back to simple concat if clips are too short

6. **Word-Level Subtitles** — 3-4 words per SRT segment with precise timing from Edge-TTS WordBoundary events. Dynamic, modern caption style instead of static sentence blocks

7. **A/B Visual Splitting** — Dynamically slices any scene longer than 4.0 seconds in half and injects a distinct secondary stock clip to forcefully reset the viewer's attention mid-sentence.

---

## Why No VPS?

| Concern | Answer |
| --- | --- |
| "Don't I need a server?" | No. Your PC has more RAM and CPU than any free VPS. |
| "What about scheduling?" | Run the script when you want. Or use Windows Task Scheduler. |
| "What about 24/7 automation?" | You don't need it. You're reviewing videos manually anyway. |
| "What about n8n?" | Overkill. A simple CLI script does the same job without Docker/Postgres overhead. |
| "What about YouTube API upload?" | Skip it. Manual upload takes 2 minutes and avoids all OAuth headaches. |

---

## Realistic Timeline

| Week | What Happens |
| --- | --- |
| 1 | Setup, first 5 test renders, fix any audio sync issues |
| 2 | First 10 public uploads (Private first), establish baseline |
| 3–4 | Identify which topics get >500 views, tune prompts |
| Month 2 | Quality improves from feedback, views start growing |
| Month 3 | 3 posts/week rhythm, algorithm starting to distribute |

The pipeline works from day one. Views come from iteration on what you feed into it — not from volume.
