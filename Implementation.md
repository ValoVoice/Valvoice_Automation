---
title: Implementation Plan
type: concept
tags:
  - implementation
  - architecture
---

# [[Implementation|Implementation Plan — YouTube Shorts Automation]]

*Return to [[README]]*

## What We're Building

A **local CLI tool** that runs on your Windows PC. You type a topic, it spits out a finished YouTube Short as an MP4. You review it, upload it yourself. No servers, no cloud, no monthly costs.

---

## Why This Approach (Design Decisions)

### Why Local, Not Cloud?
- You said you don't care about auto-uploading — you'll review and upload manually
- Your PC has 8-16GB RAM. A free VPS has 1GB. Your machine is objectively better for video rendering
- Eliminates every infrastructure headache: Docker, PostgreSQL, n8n, OAuth tokens, cron jobs, reverse proxies
- Zero recurring cost. Forever

### Why CLI, Not a Web UI?
- A Streamlit or FastAPI web UI adds dependencies, adds complexity, and solves nothing when only one person (you) is using it
- CLI is faster to build, faster to run, and easier to debug
- `python main.py --topic "..."` is simpler than opening a browser and clicking buttons

### Why No YouTube API Upload?
- YouTube OAuth setup requires a Google Cloud project, an app review, and persistent token management
- Token refresh breaks silently. You'd spend more time debugging auth than making videos
- Manual upload via YouTube Studio takes 2 minutes and gives you the chance to tweak title/description/tags before publishing
- You can always add API upload later as an optional feature if you want it

---

## The Stack (And Why Each Piece)

| Component | Tool | Why This One |
| --- | --- | --- |
| **Script Generation** | Gemini 2.5 Flash (free tier) | 1,500 free requests/day. No credit card required. Generates structured JSON. Configurable to 2.5 Pro via `.env` |
| **Voice Synthesis** | Edge-TTS | Completely free, unlimited, no API key. Generates audio AND word-level subtitles simultaneously (no Whisper) |
| **B-Roll Video** | Pexels API + Pixabay API | Pexels primary (200 req/hr), Pixabay fallback. Two separate clip libraries = double the footage pool |
| **Video Rendering** | FFmpeg (direct subprocess calls) | xfade transitions, BGM mixing, subtitle burn-in, LUFS normalization — all in one tool |
| **Background Music** | Local `songs/` folder | Royalty-free tracks from YouTube Audio Library. Random pick per video, mixed at -20dB |
| **Subtitle Burn-in** | FFmpeg `subtitles` filter | Word-level chunked SRT (3-4 words per segment) for dynamic, modern captions |
| **Keyword Validation** | YouTube autocomplete API | Free, no key needed. Checks if a topic has actual search demand before wasting API calls |
| **Entry Point** | Python argparse CLI | Zero dependencies beyond what's already needed. Simple, scriptable |

### What We're NOT Using (And Why)

| Removed | Reason |
| --- | --- |
| **n8n / Docker / PostgreSQL** | Overkill. Only needed for automated scheduling on a remote server |
| **FastAPI / uvicorn** | Only needed if something else (like n8n) calls our code via HTTP. Nothing does |
| **MoviePy** | Adds a heavy dependency that just wraps FFmpeg anyway. We call FFmpeg directly |
| **OpenAI Whisper** | Edge-TTS already generates word-level subtitles via `SubMaker`. Whisper is redundant and requires ~3GB of model weights |
| **YouTube upload scripts** | You're uploading manually. No OAuth headaches |
| **docker-compose.yml** | No Docker needed locally |
| **SSML markup** | Edge-TTS does NOT support `<emphasis>`, `<break>`, or `<mstts:express-as>` tags. Verified against GitHub docs. We use per-scene rate/pitch variation instead |
| **gemini-2.0-flash** | Shut down June 1, 2026. Migrated to `gemini-2.5-flash` |

---

## Voice Selection

> [!IMPORTANT]
> **Locked-in default voice: `en-GB-RyanNeural`** (British male, distinctive)

This is set once and used consistently across ALL videos from day one. Consistency matters — the algorithm recognizes channels by audio fingerprint and rewards audience familiarity.

**Why this voice:**
- `en-US-AvaNeural` is the Edge-TTS default. Every automation channel uses it. Viewers associate it with AI slop. Avoid entirely
- `en-US-GuyNeural` is the second most common. Still recognizable
- `en-GB-RyanNeural` is distinctive, professional, and almost never used in automation. British accent stands out in a US-dominated Shorts feed

**Where it's configured:** `.env` file → `VOICE=en-GB-RyanNeural`

Other options if you want to experiment later:

| Voice ID | Description | Notes |
| --- | --- | --- |
| `en-GB-RyanNeural` | British male, distinctive | **Default. Recommended** |
| `en-US-ChristopherNeural` | American male, professional | Good alternative |
| `en-AU-WilliamNeural` | Australian male | Very distinctive, niche appeal |
| `en-US-JennyNeural` | Female, warm | Good for lifestyle/explainer niches |

---

## Project Structure (Final)

```
Youtube Automation/
├── main.py                     ← CLI entry point (the only file you run)
├── scripts/
│   ├── __init__.py
│   ├── generate_script.py      ← Gemini → structured JSON script (A/B/C rotation)
│   ├── generate_audio.py       ← Edge-TTS → MP3 + word-level SRT (per-scene prosody)
│   ├── fetch_assets.py         ← Pexels + Pixabay → vertical stock clips (deduplicated)
│   └── render_video.py         ← FFmpeg → final 9:16 MP4 (xfade + BGM)
├── songs/                      ← Royalty-free BGM tracks (you add these)
├── topics.txt                  ← Your topic ideas (one per line)
├── requirements.txt            ← Only 4 packages
├── config.py                   ← Central path constants
├── settings.py                 ← Central environment variable logic
├── .env                        ← Your API keys (not in version control)
├── .gitignore                  ← Keeps secrets + large files out of git
├── Architecture.md             ← How-to-run guide + upload checklist
├── Research.md                 ← Your original research
├── Implementation.md           ← This implementation plan
│
│   (Created automatically when you run it:)
├── artifacts/
│   ├── output/                 ← Finished MP4s land here
│   ├── generated_scripts/      ← JSON scripts (kept for reference)
├── format_counter.json         ← Tracks A/B/C rotation (auto-managed)
└── used_clips.json             ← Tracks used Pexels+Pixabay clip IDs (auto-managed)
```

> [!IMPORTANT]
> **Disk cleanup is built into `main.py`.** After a successful render, the pipeline automatically deletes the raw Pexels clips (`artifacts/video/assets/`), the intermediate audio file, and the subtitle file. Only the final MP4 in `artifacts/output/` and the script JSON in `artifacts/generated_scripts/` are kept.

---

## Implementation Phases

### Phase 1 — Foundation (Do First)
**Goal:** Get each module working in isolation, then wire them together for ONE end-to-end video.

| Step | File | What It Does | Status |
| --- | --- | --- | --- |
| 1.0 | `main.py --script-only` | **Test Gemini FIRST.** Verify it returns valid, parseable JSON. Cheapest test — no FFmpeg, no Pexels, no audio | Ready to test |
| 1.1 | `scripts/generate_script.py` | Calls Gemini 2.5 Flash, gets back JSON with 6 scenes. A/B/C format rotation built in. Markdown fence stripping + auto-retry on parse failure | ✅ Done |
| 1.2 | `scripts/generate_audio.py` | Per-scene Edge-TTS generation with rate/pitch variation. Word-level subtitle chunking (3-4 words/segment). -16 LUFS normalization | ✅ Done |
| 1.3 | `scripts/fetch_assets.py` | Pexels search with 3-tier fallback + Pixabay 4th tier + `used_clips.json` deduplication | ✅ Done |
| 1.4 | `scripts/render_video.py` | FFmpeg: trim to `CLIP_DURATION` → scale/crop 1080x1920 → xfade transitions → add audio → mix BGM at -20dB → burn word-level subs → `yuv420p` + `faststart` | ✅ Done |
| 1.5 | `main.py` | Wires steps together. YouTube autocomplete keyword check. Disk cleanup. `--skip-keyword-check` flag | ✅ Done |

**Why this order:** Each step depends on the output of the previous one. Script → Audio → Visuals → Render.

### Phase 2 — Hardening (Do After First Successful Render)
**Goal:** Handle the things that WILL break in real usage.

| Step | What | Status |
| --- | --- | --- |
| 2.1 | **Gemini JSON retry** | ✅ Done — retries once on parse failure |
| 2.2 | **Pexels fallback search** | ✅ Done — 3-tier fallback |
| 2.3 | **FFmpeg error handling** | ✅ Done — clip validation, stderr output |
| 2.4 | **Minimum scene threshold** | ✅ Done — aborts if <2 clips |
| 2.5 | **Windows path escaping** | ✅ Done — `_get_safe_srt_path()` |
| 2.6 | **Disk cleanup** | ✅ Done — auto-deletes assets after render |
| 2.7 | **Clip deduplication** | ✅ Done — `used_clips.json` tracking (Pexels + Pixabay) |
| 2.8 | **Format rotation** | ✅ Done — A/B/C via `format_counter.json` |
| 2.9 | **Keyword validation** | ✅ Done — YouTube autocomplete pre-check |
| 2.10 | **BGM mixing** | ✅ Done — Random track from `songs/` at -20dB under voiceover |
| 2.11 | **Word-level subtitles** | ✅ Done — 3-4 words per SRT segment via Edge-TTS WordBoundary |
| 2.12 | **xfade transitions** | ✅ Done — 0.3s cross-fade between clips (falls back to hard cut) |
| 2.13 | **Clip duration control** | ✅ Done — `CLIP_DURATION` env var (default 4s) |
| 2.14 | **Pixabay fallback** | ✅ Done — 4th-tier search when Pexels exhausted |

### Phase 3 — Quality Polish (Do After 10+ Successful Renders)
**Goal:** Make the videos actually good enough to compete with human-edited Shorts.

| Step | What | Why It Matters | Risk |
| --- | --- | --- | --- |
| 3.1 | **Subtitle styling** | Bold white text, black outline, bottom-center with margin | ✅ Done |
| 3.2 | **Scene transitions (xfade)** | 0.3s cross-fade between clips via FFmpeg `xfade` | ✅ Done |
| 3.3 | **A/B visual splitting** | Slice scenes in half, switch visuals mid-sentence for retention | High | ✅ Done (via `main.py`) |
| 3.4 | **Silence removal** | Trim dead air from Edge-TTS output | **⚠️ HIGH RISK** |
| 3.5 | **Aspect ratio intelligence** | Center-crop landscape clips to 9:16. Already implemented | ✅ Done |

> [!WARNING]
> **Phase 3.4 — Silence removal is HIGH RISK.** FFmpeg's `silenceremove` filter doesn't work cleanly on Edge-TTS output because neural TTS produces low-amplitude gaps, not true silence. Will clip mid-word without careful per-voice threshold tuning. **Do not automate blindly.**

### Phase 4 — Iteration & Growth Tools (Do After First Month)

| Step | What | Status |
| --- | --- | --- |
| 4.1 | **Batch generation** (`--count N`) | ✅ Implemented, needs real-world testing |
| 4.2 | **Topic generation from winners** | Not started |
| 4.3 | **AI background music** (Miraflow) | Not started |

---

## YouTube Compliance (Mandatory)

> [!CAUTION]
> **YouTube's July 2025 "inauthentic content" policy is actively enforced.** Channels have been permanently terminated, not just demonetized. This section is non-negotiable.

### What YouTube Detects (And How We Counter It)

| Detection Signal | How Our Pipeline Handles It |
| --- | --- |
| **Template uniformity** (same structure every video) | A/B/C format rotation — myth-bust, hidden insight, specific number |
| **Flat TTS monotone** (constant rate/pitch) | Per-scene rate/pitch variation in `generate_audio.py` |
| **Repeated stock clips** across videos | `used_clips.json` dedup + Pixabay secondary source |
| **Low information gain** (generic content) | Niche-tuned prompt forces specific names, numbers, papers |
| **Mass-production upload pattern** | You upload manually, 3x/week max |
| **Undisclosed AI content** | AI disclosure reminder built into CLI output |
| **Zero search demand** topics | YouTube autocomplete check before generation |
| **Hard cuts between scenes** | 0.3s xfade cross-fade transitions |
| **No background music** | Random BGM at -20dB from `songs/` folder |
| **Static subtitle blocks** | Word-level chunking — 3-4 words per segment, dynamically timed |

### Upload Checklist (Every Single Video)

1. ☐ Watch the first 10 seconds and last 10 seconds for audio/video sync
2. ☐ Review and fix the title — this is your biggest SEO lever
3. ☐ Set category to **28 (Science & Technology)** — not People & Blogs
4. ☐ Enable **"Altered or synthetic content"** label — EVERY video, no exceptions
5. ☐ Schedule upload for Tue/Thu/Sat at 11am IST — never 2 videos within 8 hours
6. ☐ Add description with keywords and newsletter link

---

## Anti-Shadowban Engineering

### Built Into the Gemini Prompt (generate_script.py)
- **Hook in first 3 words.** Slow intro = massive drop-off = algorithm buries the channel
- **Information Gain over generic content.** Specific architecture names, paper titles, real benchmarks
- **No filler phrases.** "In this video", "Let's dive in", "Stay tuned" = low-effort signals
- **A/B/C format rotation.** No two consecutive videos follow the same structural arc

### Built Into the Audio Pipeline (generate_audio.py)
- **Per-scene rate/pitch variation.** Breaks the flat TTS monotone that viewers and algorithms detect
- **-16 LUFS normalization.** Consistent volume across all videos

### Built Into the Asset Pipeline (fetch_assets.py)
- **Clip deduplication.** Same Pexels clip never appears in two videos
- **3-tier fallback search.** Always finds a clip, but never reuses one

### Built Into the Render Pipeline (render_video.py)
- **`yuv420p` pixel format** — universal player compatibility
- **`faststart` moov atom** — instant web streaming, no buffering

### Built Into Your Publishing Strategy (Manual)
- **Private first 20 videos** — review quality before going public
- **3x/week cadence** (Tue/Thu/Sat) — looks like a real creator, not a bot
- **AI disclosure every time** — mandatory in 2026, protects you from automatic flagging
- **Non-default voice** (`en-GB-RyanNeural`) — distinctive, almost never used in automation

---

## Prerequisites (What You Need Before Any Code Runs)

### Already Done
- [x] Project directory exists
- [x] Research.md completed
- [x] Architecture.md created
- [x] Implementation.md created
- [x] FFmpeg installed at `C:\ffmpeg\bin`
- [x] Python venv created with all dependencies

### You Need To Do
1. **Create `.env` file** from the template
   ```powershell
   copy .env.example .env
   ```
2. **Get a Gemini API key** (free) → [aistudio.google.com](https://aistudio.google.com)
3. **Get a Pexels API key** (free) → [pexels.com/api](https://www.pexels.com/api/)
4. **Paste both keys into `.env`**

---

## What Exists Now vs. What Needs Work

| File | Status | Notes |
| --- | --- | --- |
| `main.py` | ✅ Done | CLI, keyword check, per-scene audio, disk cleanup, AI disclosure reminder |
| `scripts/generate_script.py` | ✅ Done | Gemini 2.5 Flash, A/B/C rotation, configurable model, retry logic |
| `scripts/generate_audio.py` | ✅ Done | Per-scene prosody, word-level SRT chunking, -16 LUFS normalization |
| `scripts/fetch_assets.py` | ✅ Done | 4-tier fallback (Pexels→broad→generic→Pixabay), deduplication |
| `scripts/render_video.py` | ✅ Done | xfade transitions, BGM mixing, CLIP_DURATION control, Windows path escaping |
| `.env.example` | ✅ Done | 7 variables: API keys, niche, voice, model, clip duration, Pixabay |
| `requirements.txt` | ✅ Done | 4 packages: `edge-tts`, `requests`, `google-generativeai`, `python-dotenv` |
| `topics.txt` | ✅ Done | 10 CS/AI starter topics |
| `.gitignore` | ✅ Done | Covers secrets + generated files + state files |

---

## Recommended Execution Order

```text
Step 1: Create .env with API keys
        ↓
Step 2: Test Gemini via --script-only
        python main.py --script-only --topic "How attention works"
        ↓
Step 3: Test full pipeline with ONE topic
        python main.py --topic "How Git stores data internally"
        ↓
Step 4: Test batch mode with 3 topics
        python main.py --topics-file topics.txt --count 3
        ↓
Step 5: Review videos, upload first batch manually
```

---

## Risk Assessment

| Risk | Likelihood | Mitigation |
| --- | --- | --- |
| Gemini returns invalid JSON | Medium | Strip markdown fences + retry once (done) |
| Edge-TTS breaks (Microsoft patches endpoint) | Low | Fallback: **kokoro-tts** (free, local). NOT pyttsx3 |
| Pexels returns no results | High | 3-tier fallback search (done) |
| Same clips across videos | High (without dedup) | `used_clips.json` tracking (done) |
| Template uniformity detection | High (without rotation) | A/B/C format rotation (done) |
| FFmpeg crashes on corrupt clip | Medium | File size validation >50KB (done) |
| Windows path issues | High | `_get_safe_srt_path()` (done) |
| Flat TTS monotone detected | Medium | Per-scene rate/pitch variation (done) |
| Disk fills up | Certain (without cleanup) | Auto-delete after render (done) |
| YouTube flags undisclosed AI | High (without label) | AI disclosure reminder in CLI output (done) |
| Zero-demand topics wasting API calls | Medium | YouTube autocomplete check (done) |
| Shadowban / algorithmic suppression | Medium (at scale) | Non-default voice, format rotation, low-volume cadence, human review gate |
