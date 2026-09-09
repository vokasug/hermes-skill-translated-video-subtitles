---
name: translated-video-subtitles
description: Use when a video needs translated, burned-in subtitles.
version: 1.0.0
license: MIT
platforms: [macos]
metadata:
  hermes:
    tags: [video, subtitles, transcription, translation, ffmpeg, yt-dlp, mlx-whisper]
    related_skills: [yt-dlp, mlx-whisper]
---

# Translated Video Subtitles

Owns the end-to-end workflow for "cut or download this clip, transcribe it, translate the speech, burn subtitles, verify, and send the MP4". Use `yt-dlp` for downloading/cutting and `mlx-whisper` for STT; this skill owns cue building, translation text rules, rendering, and verification.

## Procedure

1. **Identify the source and language before downloading or STT.** For YouTube, get title,
   duration, language, and available captions with `yt-dlp --js-runtimes node`. If metadata is
   ambiguous, run a short language-detect fragment. Never guess the language from habit.

2. **Cut or download the clip as MP4 H.264+AAC.** For source intervals, cut during download:

   ```bash
   ~/.local/bin/yt-dlp --js-runtimes node --no-playlist \
     --download-sections '*HH:MM:SS-HH:MM:SS' --force-keyframes-at-cuts \
     -S 'res:720,vcodec:h264,ext:mp4:m4a' --merge-output-format mp4 \
     -o '$HOME/result-yt-dlp/$(date +%F)_name.%(ext)s' '<URL>'
   ```

   Verify immediately with `ffprobe`: expected duration, nonzero size, H.264 video, AAC audio.

3. **Transcribe with word timestamps:**

   ```bash
   ~/.local/bin/mlx_whisper \
     --model ~/.local/share/models/whisper-podlodka-turbo-MLX-q8 \
     --language <detected> --condition-on-previous-text False \
     --word-timestamps True --output-format all \
     --output-dir <stt-out-dir> <clip.mp4>
   ```

   Source-language platform captions may be downloaded as a terminology cross-check, but local
   STT remains the timing source.

4. **Build translated cues at word boundaries.** Split by speaker or phrase; no overlaps. No cue
   may be shorter than 2.0 s. First merge short reactions/questions with an adjacent cue; if that
   would bury a line, extend into neighbouring silence by a few hundred ms while keeping a small
   gap and never overlapping the next cue. Prefer two readable lines; with large mobile subtitles,
   allow three balanced lines. Put manual breaks at phrase boundaries and avoid orphan words.
   Rebase cue times to zero when the input is a downloaded section.

   **Subtitle text rule:** do not use long dashes (`—`, `–`) in subtitle text. Replace them with
   a hyphen `-` or rephrase. The converter must reject any SRT that still contains them.

   If the user requires an exact term, name, or final phrase, assert that exact string in the
   final SRT and inspect it on screen. Write SRT first, then convert it to cue JSON:

   ```bash
   python3 <SKILL_DIR>/scripts/srt_to_cues.py translated.srt cues.json --min-duration 2.0
   ```

5. **Prepare the frame before burning.** Inspect a representative frame for embedded letterbox
   bars. If dark borders are part of the video, measure the stable crop with:

   ```bash
   ffmpeg -i '<clip.mp4>' -vf cropdetect=limit=24:round=2 -f null -
   ```

   Crop and cover-scale first, add `setsar=1`, and only then overlay subtitles on the active
   image. Do not place subtitles in a letterbox area.

6. **Burn the subtitles.** Check whether the local ffmpeg has a native subtitle renderer:

   ```bash
   ffmpeg -hide_banner -h filter=subtitles
   ```

   If `subtitles`/`drawtext` is unavailable, do not install packages silently. Use the bundled
   deterministic PNG-overlay fallback:

   ```bash
   swift <SKILL_DIR>/scripts/render_subtitle_cues.swift \
     cues.json cue_pngs 1280 720 51 28 8

   python3 <SKILL_DIR>/scripts/burn_cue_pngs.py \
     --video '<clip.mp4>' --cues cues.json --png-dir cue_pngs \
     --out '<final.mp4>' --width 1280 --height 720 [--crop 'W:H:X:Y']
   ```

   For 720p full-frame mobile output, start with 51 pt bold text, 28 px bottom margin, and an
   8 px black outline. Scale these values with frame height. The fallback renders one transparent
   full-frame PNG per cue, draws a multi-offset black underlay with white fill on top, applies one
   timed ffmpeg overlay per cue, and copies audio unchanged.

7. **Verify before delivery:**
   - `ffprobe` final duration, codecs, dimensions, SAR/DAR, and size.
   - Decode the whole output: `ffmpeg -v error -i final.mp4 -f null -`.
   - Compare source/output audio hashes when audio was copied:
     `ffmpeg -i <file> -map 0:a -f hash -hash sha256 -`.
   - Extract frames inside the first, middle, and final cue and inspect them visually. Use a
     separate ffmpeg invocation per frame.
   - Check SRT/JSON for the exact required phrase, monotonic cue timing, no long dashes, and
     minimum cue duration.
   - For Telegram, keep MP4 H.264+AAC below 50 MB and send with `MEDIA:/absolute/path.mp4`.

## Pitfalls

- Never substitute platform captions for the requested transcription; use them only to check
  names, terms, and uncertain words.
- Keep `cues.json` as the single source of truth for overlay timing. Regenerating PNGs or the
  overlay chain must not change cue times independently.
- Use full-frame alpha PNGs at the output video resolution so overlay coordinates cannot drift.
- Render very thick outlines as a multi-offset black underlay with white fill on top. A large
  negative `NSAttributedString.strokeWidth` floods glyph interiors and makes text read as black.
- Do not composite subtitles frame-by-frame in Python when one PNG per cue plus timed overlays is
  sufficient; it is slower and adds avoidable failure points.
- Do not change audio when the task is subtitles only; copy it and prove with a matching hash.
- If a user-specified phrase is required, validate the literal string in the final SRT and inspect
  the final visible frame; a successful encode is not proof the phrase made it onto screen.
