# PROJECT_MAP.md
Return to [[README]]

## File Responsibility Map

| File | Purpose | Status | Last Changed |
|------|---------|--------|---------------|
| main.py | CLI entry for AI/CS explainer channel, A/B split logic | ✅ Working | B-roll keyword array fix & cleanup verified |
| main_promo.py | CLI entry for Acrylic/product promo channel (OBS + overlays) | ✅ Working | Verified with Universal UI Fit + Box-Blur Background framing |
| convert_photos_to_clips.py | Converts static screenshots to promo MP4 stand-in videos | ✅ Working | Upgraded to Universal UI Fit + Glassmorphic Box-Blur Background (banned center crop) |
| settings.py | Env vars, fail-fast validation, NVENC detection | ✅ Working | NVENC auto-detect added |
| scripts/generate_script.py | Gemini script generation | ✅ Working | Migrated to 2-keyword visual schema |
| scripts/generate_audio.py | Edge-TTS / Chatterbox audio | ✅ Working | No changes pending |
| scripts/fetch_assets.py | Pexels download + fallback | ✅ Working | Renamed visual_search to visual_keyword |
| scripts/render_video.py | FFmpeg render, NVENC/CPU switch, drawtext promo overlays | ✅ Working | Upgraded render_promo() with Universal UI Fit & Box-Blur Background per DEC-0002 |
| test_split.py | Isolated A/B split test | ✅ Working | Passed validation |
| [[AGENTS.md]] | Agent behavior rules | ✅ Current | Added PROJECT_MAP requirement |

## Status Legend
- ✅ Working — tested, no known issues
- 🔧 In progress — actively being modified
- ⚠️ Broken — known issue, needs fix
- 📋 Planned — not started, future phase

## What's Left (Current Phase)
- [x] Finish visual_keywords migration across generate_script.py + fetch_assets.py
- [x] Update array bounds checking in main.py
- [x] Batch test 5 videos, confirm b-roll relevance holds
- [x] Add AI-disclosure toggle reminder to upload checklist
- [x] Implement with_retry wrapper and try-finally guaranteed cleanup in main.py

## Next Phase (Do Not Start Yet)
- [ ] Kokoro TTS local migration
- [ ] Local AI b-roll generation (Wan 2.1)
- [ ] Analytics feedback automation

---
title: YouTube Automation Project
type: project
status: active
created: 2026-07-29
updated: 2026-07-30
tags:
  - project
  - automation
  - youtube
sources:
  - Youtube Automation/Implementation.md
  - Youtube Automation/Architecture.md
  - Youtube Automation/README.md
---

# 🚀 Project: YouTube Automation

**Description**: A local Windows CLI tool that generates fully-produced YouTube Shorts (9:16 MP4) from a single topic. Uses Gemini AI for scripting, Edge-TTS for voiceover, Pexels + Pixabay for b-roll, and FFmpeg for rendering. The user reviews and manually uploads the final MP4s.

> See the full YouTube Automation MOC for a curated map of all related notes.

---

## 🛠️ Pipeline Architecture

The pipeline runs in five sequential stages. Each module depends on the output of the previous one. For deep dives on how each works, see their dedicated atomic nodes:

1. **Script Generator** — Uses gemini-ai to write JSON (A/B/C format rotation)
2. **Voice Generation** — Uses edge-tts to make audio and word-level subtitles
3. **B-Roll Sourcing** — Uses pexels-api & pixabay-api to find stock footage
4. **Video Rendering** — Uses ffmpeg to composite the final MP4
5. **Upload Pipeline** — Manual upload via YouTube Studio with checklists

---

## 📦 Tech Stack

| Component | Tool | Notes |
|---|---|---|
| Script Generation | Gemini 2.5 Flash | 1,500 free req/day. Configurable to 2.5 Pro via `.env` |
| Voice Synthesis | Edge-TTS | Free, unlimited. Generates audio AND word-level SRTs |
| B-Roll | Pexels API + Pixabay API | 4-tier fallback; deduplication via `used_clips.json` |
| Video Render | FFmpeg | xfade, BGM mixing, subtitle burn-in, LUFS normalization |
| Background Music | Local `songs/` folder | Random royalty-free track at -20dB per video |
| Entry Point | Python argparse CLI | `python main.py --topic "..."` |

---

## 🔄 Anti-Detection Systems
*(See YouTube Compliance & Anti-Shadowban for full details)*

1. **A/B/C Format Rotation** — `format_counter.json` cycles myth-bust, hidden-insight, specific-number formats
2. **Clip Deduplication** — `used_clips.json` tracks every Pexels/Pixabay clip ID ever used
3. **Per-Scene Prosody Variation** — Each scene has slightly different TTS rate (+10%–+18%) and pitch (-2Hz to +2Hz)
4. **Background Music** — Unique audio fingerprint per video
5. **xfade Transitions** — 0.3s cross-fade vs. hard cuts
6. **Word-Level Subtitles** — 3-4 words per SRT segment for dynamic caption feel

---

## 🧪 Experiments & Prompt Versions

### Script Generation
| Version | Date | Description | Result |
|---|---|---|---|
| V1 | (baseline) | YouTube Script Prompt V1 with A/B/C rotation | Pending real-world testing |

### Voice
| Decision | Value | Reason |
|---|---|---|
| Default Voice | `en-GB-RyanNeural` | Distinctive British accent. Avoids `en-US-AvaNeural` (overused in automation channels) |

### Model
| Model | Status | Notes |
|---|---|---|
| `gemini-2.5-flash` | ✅ Active | Free tier, 1500 req/day |
| `gemini-2.0-flash` | ❌ Deprecated | Shut down June 1, 2026. Do NOT use |
| `gemini-2.5-pro` | Optional | ~₹0.05/script, better narrative quality |

---

## ✅ Implementation Status

| Phase | Module | Status |
|---|---|---|
| Phase 1 | `generate_script.py` | ✅ Done |
| Phase 1 | `generate_audio.py` | ✅ Done |
| Phase 1 | `fetch_assets.py` | ✅ Done |
| Phase 1 | `render_video.py` | ✅ Done |
| Phase 1 | `main.py` (wiring) | ✅ Done |
| Phase 2 | Gemini JSON retry | ✅ Done |
| Phase 2 | Pexels 3-tier fallback | ✅ Done |
| Phase 2 | FFmpeg error handling | ✅ Done |
| Phase 2 | Clip deduplication | ✅ Done |
| Phase 2 | Word-level subtitles | ✅ Done |
| Phase 3 | A/B visual splitting (mid-scene) | ⬜ Not started |
| Phase 3 | Silence removal | ⚠️ HIGH RISK — not started |
| Phase 4 | Topic generation from winners | ⬜ Not started |

---

## 🐛 Bugs & Fixed Issues
*(Critical fixes — AI must never revert these)*
- **`gemini-2.0-flash` removed**: Was shut down June 1, 2026. All model calls use `gemini-2.5-flash`.
- **Windows path escaping**: `_get_safe_srt_path()` added to `render_video.py` — required on Windows due to spaces in paths.
- **SSML markup removed**: Edge-TTS does NOT support `<emphasis>`, `<break>`, or `<mstts:express-as>` tags. Use per-scene rate/pitch variation instead.
- **UI Promo Center-Crop Ban (DEC-0002)**: Center-cropping (`crop=1080:1920`) destroyed 68% of horizontal widescreen desktop footage in `main_promo.py` and `convert_photos_to_clips.py`, deleting left/right UI sidebars and docks. All promo screen recordings and screenshots MUST use **Universal UI Fit + Glassmorphic Box-Blur Background** (`split[bg][fg];...overlay=(W-w)/2:(H-h)/2`). Never re-introduce center cropping on UI clips.

---

## 📋 Upload Checklist (Every Single Video)
1. ☐ Watch first and last 10 seconds for audio/video sync
2. ☐ Review and fix the title — biggest SEO lever
3. ☐ Set category to **28 (Science & Technology)**
4. ☐ Enable **"Altered or synthetic content"** label — mandatory, every video
5. ☐ Schedule for **Tue/Thu/Sat at 11am IST**
6. ☐ Add description with keywords

---

## 🔗 Related Nodes
- MOC: YouTube Automation MOC
- Concepts: Prompt Engineering, YouTube Compliance, Anti-Template Systems
- Entities: Gemini AI, Edge-TTS, Pexels API, Pixabay API, FFmpeg


---
title: B-Roll Sourcing (YouTube Automation)
type: workflow
status: active
created: 2026-07-30
updated: 2026-07-30
tags:
  - workflow
  - video
  - youtube
sources:
  - docs/Architecture/Implementation.md
---

# 🎥 Workflow: B-Roll Sourcing

**Description**: The third stage of the YouTube Automation pipeline. Dynamically fetches vertical stock footage matching the scene topics.

## System Dependencies
* Upstream: Script Generator (supplies search terms)
* Core Services: Pexels API and Pixabay API
* Downstream: Video Rendering

## Key Features
* **4-Tier Fallback Search**:
  1. Pexels exact search
  2. Pexels broad keyword search
  3. Pexels generic fallback
  4. Pixabay final fallback
* **Clip Deduplication**: Tracks every used clip in `state/used_clips.json` to guarantee the same clip never appears across two videos.

## Related
* Project: YouTube Automation
 ---
title: Script Generator (YouTube Automation)
type: workflow
status: active
created: 2026-07-30
updated: 2026-07-30
tags:
  - workflow
  - scripting
  - youtube
sources:
  - docs/Architecture/Implementation.md
---

# 📝 Workflow: Script Generator

**Description**: The first stage of the YouTube Automation pipeline. Converts a raw topic from `topics.txt` into a structured, 6-scene JSON script.

## System Dependencies
* Upstream: `topics.txt`
* Core Service: Gemini 2.5 Flash (via `google-generativeai` package)
* Downstream: Voice Generation

## Key Features
* **A/B/C Format Rotation**: Automatically cycles through Myth-Bust, Hidden Insight, and Specific Number arcs.
* **JSON Parsing**: Strips markdown fences from the API response and auto-retries once on parsing failure.

## Current Prompts in Use
* YouTube Script V1 (A/B/C Baseline)

## Related
* Project: YouTube Automation
* Concept: Prompt Engineering
 ---
title: Video Rendering (YouTube Automation)
type: workflow
status: active
created: 2026-07-30
updated: 2026-07-30
tags:
  - workflow
  - ffmpeg
  - youtube
sources:
  - docs/Architecture/Implementation.md
---

# 🎞️ Workflow: Video Rendering

**Description**: The final automated stage of the YouTube Automation pipeline. Composites the audio, video clips, and subtitles into a single 9:16 MP4 file.

## System Dependencies
* Upstream: Voice Generation (Audio + SRT) & B-Roll Sourcing (MP4 clips)
* Core Service: FFmpeg (Local binary subprocess)
* Downstream: `output/` directory (ready for manual upload)

## Key Features
* **Aspect Ratio Intelligence (Dual Pipeline)**: 
  * **Explainer B-Roll (`render_video`)**: Natively center-crops stock video to 1080x1920.
  * **Promo / UI Showcases (`render_promo` & `convert_photos_to_clips`)**: Enforces **Universal UI Fit & Glassmorphic Box-Blur Background** per DEC-0002. Never center-crops widescreen desktop recordings, preserving 100% of side navigation toolbars and drawers.
* **xfade Transitions**: 0.3s cross-fades between clips to avoid algorithmic detection of hard cuts.
* **BGM Mixing & Native Sound Integration**: 
  * Explainer mode randomly selects a `.mp3` from `songs/` and mixes it at -20dB under voiceover.
  * Promo mode exports silent audio beds (optional short spoken hook at 00:00) so trending sounds can be natively attached at upload without copyright collisions.
* **Subtitle Burn-in & Overlays**: Hardcodes SRT captions in explainer mode, while utilizing top/third drawtext banners over dark blurred backgrounds in promo mode.

## Related
* Project: YouTube Automation
* Decisions: DEC-0002 - Universal UI Fit & Box-Blur Background
 ---
title: Voice Generation (YouTube Automation)
type: workflow
status: active
created: 2026-07-30
updated: 2026-07-30
tags:
  - workflow
  - audio
  - youtube
sources:
  - docs/Architecture/Implementation.md
---

# 🔊 Workflow: Voice Generation

**Description**: The second stage of the YouTube Automation pipeline. Converts the generated JSON script text into high-quality TTS audio and word-level subtitles.

## System Dependencies
* Upstream: Script Generator
* Core Service: Edge-TTS (Python library)
* Downstream: Video Rendering

## Key Features
* **Per-Scene Prosody Variation**: Varies speech rate (+10% to +18%) and pitch (-2Hz to +2Hz) to defeat monotone detection.
* **Word-Level SRT Chunking**: Uses `SubMaker` to parse `WordBoundary` events into 3-4 word subtitle blocks.
* **Normalization**: Mastered to -16 LUFS.

## Configuration
* Voice: `en-GB-RyanNeural`

## Related
* Project: YouTube Automation

---

## 🎵 Background Music (BGM) Guidelines
Place 5-10 royalty-free music tracks inside the `songs/` directory. The pipeline randomly picks one per video and mixes it at -20dB under the voiceover. Supported formats: `.mp3`, `.wav`, `.m4a`, `.ogg`.

### Where to Get Free Tracks
1. **YouTube Audio Library** (BEST — guaranteed safe for YouTube)
   - Go to https://studio.youtube.com → Audio Library
   - Filter by: Genre, Mood, Duration. Download `.mp3` files directly (pre-cleared for YouTube use).
2. **Pixabay Music** (also safe)
   - Go to https://pixabay.com/music/
   - Filter for "chill", "ambient", "electronic" (CC0 license — no attribution needed).

### Best Practices
- Pick ambient/chill tracks — they shouldn't compete with the voiceover.
- Avoid tracks with lyrics — they distract from narration.
- Get tracks that are 60-90 seconds long (matches Shorts length). The pipeline automatically loops the track if it's shorter than the video.

