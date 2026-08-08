# SESSION_LOG.md
Return to [[README]]

## 2026-08-03
### Promo Pipeline UI Framing Standardization & Center-Crop Ban (DEC-0002)
- **Context/Problem**: Center-cropping (`crop=1080:1920`) in `main_promo.py` and `convert_photos_to_clips.py` deleted 68% of horizontal widescreen desktop footage, slicing off Acrylic's left quick-links dock and right preferences drawers.
- **Decision**: Strictly banned center-cropping across all promo and UI pipelines. Implemented the **Universal UI Fit + Glassmorphic Box-Blur Background** framing architecture via FFmpeg (`split[bg][fg];...overlay=(W-w)/2:(H-h)/2`). 
- **Rationale**: 
  1. Zero UI Truncation: Video stream scaled to fit fully within the vertical canvas. 
  2. Glassmorphic Aesthetics: Background blurred (`boxblur=25:10`) and darkened.
  3. Optimized text overlay layering over the dark blurred background. 
  4. Idempotency for already-vertical clips.

### Explainer Pipeline TTS Chunking & Artifact Preservation (DEC-0003)
- **Context/Problem**: Long narration scenes caused Chatterbox TTS to exceed its context limit, leading to truncated or garbage audio mid-script. Failed pipeline runs were silently erasing their temporary audio/asset folders via a blind `finally` block, masquerading as success.
- **Decision**: 
  1. **Clause-Level Chunking**: Implemented `chunk_narration`. Scripts are split by sentence punctuation (`[.?!]`) and bounded by a 25-word cap per chunk. Chunks are stitched together via `numpy.concatenate`.
  2. **Decoupled Tone Variables**: Split global `EXAGGERATION` into `EXAGGERATION_EXPLAINER` (0.5) and `EXAGGERATION_PROMO_HOOK` (0.7).
  3. **Artifact Preservation**: Wrapped the `finally` block in `main.py` with a `success` boolean flag. Temporary files are preserved on disk on failure.

## 2026-08-02
Verified try/finally disk cleanup in main.py and deleted temporary ad-hoc patch scripts (patch1-3.py, refactor.py). Built dedicated promo channel pipeline via main_promo.py for OBS screen captures and text overlays. Reused render_video.py NVENC encoding and xfade logic (via render_promo) to maintain single-source encoding without duplicating files.

## 2026-08-01
Fixed b-roll relevance — moved from string concat hack to Gemini-generated 2-keyword arrays. Added array bounds checking. Migrated SDK to google-genai to bypass grpcio DLL block. NVENC confirmed working, ~25s render time.

## 2026-07-30
Initial pipeline working end-to-end. Script → audio → b-roll → render → manual upload. Voice: en-US-ChristopherNeural.
