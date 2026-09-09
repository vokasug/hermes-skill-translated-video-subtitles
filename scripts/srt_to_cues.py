#!/usr/bin/env python3
"""Convert SRT to cue JSON and enforce subtitle timing/text rules."""

import argparse
import json
import re
import sys
from pathlib import Path

TIME_RE = re.compile(r"(\d\d):(\d\d):(\d\d),(\d\d\d)\s+-->\s+(\d\d):(\d\d):(\d\d),(\d\d\d)")
LONG_DASHES = ("—", "–")


def to_seconds(match: re.Match[str], offset: int) -> float:
    hours = int(match.group(offset))
    minutes = int(match.group(offset + 1))
    seconds = int(match.group(offset + 2))
    milliseconds = int(match.group(offset + 3))
    return hours * 3600 + minutes * 60 + seconds + milliseconds / 1000.0


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("srt", type=Path, help="input SRT")
    parser.add_argument("json", type=Path, help="output cue JSON")
    parser.add_argument("--min-duration", type=float, default=2.0, help="minimum cue duration in seconds")
    args = parser.parse_args()

    text = args.srt.read_text(encoding="utf-8").strip()
    blocks = [block for block in re.split(r"\n\s*\n", text) if block.strip()]
    cues = []
    previous_end = 0.0

    for index, block in enumerate(blocks, start=1):
        lines = block.splitlines()
        if len(lines) < 3:
            sys.exit(f"cue {index}: expected number, timing, and text lines")
        match = TIME_RE.match(lines[1])
        if not match:
            sys.exit(f"cue {index}: invalid timing line: {lines[1]!r}")
        start = to_seconds(match, 1)
        end = to_seconds(match, 5)
        duration = end - start
        cue_text = "\n".join(lines[2:])

        if duration <= 0:
            sys.exit(f"cue {index}: non-positive duration")
        if duration + 1e-9 < args.min_duration:
            sys.exit(f"cue {index}: duration {duration:.3f}s below minimum {args.min_duration:.3f}s")
        if start < previous_end - 1e-9:
            sys.exit(f"cue {index}: overlaps previous cue")
        bad_dashes = [dash for dash in LONG_DASHES if dash in cue_text]
        if bad_dashes:
            sys.exit(f"cue {index}: long dash forbidden: {' '.join(bad_dashes)}")

        previous_end = end
        cues.append({"start": start, "end": end, "text": cue_text})

    if not cues:
        sys.exit("no cues found")
    args.json.parent.mkdir(parents=True, exist_ok=True)
    args.json.write_text(json.dumps(cues, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {len(cues)} cues to {args.json}; min duration {args.min_duration:.3f}s; no long dashes")


if __name__ == "__main__":
    main()
