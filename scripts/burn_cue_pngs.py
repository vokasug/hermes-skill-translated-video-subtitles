#!/usr/bin/env python3
"""Burn per-cue transparent PNGs into video with timed ffmpeg overlays."""

import argparse
import json
import subprocess
import sys
from pathlib import Path

LONG_DASHES = ("—", "–")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--video", required=True, type=Path, help="input video")
    parser.add_argument("--cues", required=True, type=Path, help="JSON list of {start,end,text}")
    parser.add_argument("--png-dir", required=True, type=Path, help="directory containing cue_01.png...")
    parser.add_argument("--out", required=True, type=Path, help="output MP4")
    parser.add_argument("--width", type=int, default=1280)
    parser.add_argument("--height", type=int, default=720)
    parser.add_argument("--crop", help="optional pre-crop as W:H:X:Y before cover-scaling")
    parser.add_argument("--crf", type=int, default=20)
    parser.add_argument("--preset", default="medium")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    cues = json.loads(args.cues.read_text(encoding="utf-8"))
    if not cues:
        sys.exit("cues.json is empty")

    pngs = []
    previous_end = 0.0
    for index, cue in enumerate(cues, start=1):
        start = float(cue["start"])
        end = float(cue["end"])
        text = str(cue["text"])
        if end <= start:
            sys.exit(f"cue {index} has non-positive duration")
        if start < previous_end:
            sys.exit(f"cue {index} overlaps previous cue")
        bad_dashes = [dash for dash in LONG_DASHES if dash in text]
        if bad_dashes:
            sys.exit(f"cue {index}: long dash forbidden: {' '.join(bad_dashes)}")
        previous_end = end

        png = args.png_dir / f"cue_{index:02d}.png"
        if not png.is_file():
            sys.exit(f"missing rendered PNG: {png}")
        pngs.append(png)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    scale_crop = (
        f"scale={args.width}:{args.height}:force_original_aspect_ratio=increase:flags=lanczos,"
        f"crop={args.width}:{args.height},setsar=1"
    )
    if args.crop:
        base = f"[0:v]crop={args.crop},{scale_crop}[base]"
    else:
        base = f"[0:v]{scale_crop}[base]"

    filter_parts = [base]
    previous = "[base]"
    for index, cue in enumerate(cues, start=1):
        start = float(cue["start"])
        end = float(cue["end"])
        label = f"[v{index}]"
        filter_parts.append(
            f"{previous}[{index}:v]overlay=0:0:enable='between(t,{start:.3f},{end:.3f})'{label}"
        )
        previous = label

    command = ["ffmpeg", "-y", "-i", str(args.video)]
    for png in pngs:
        command.extend(["-i", str(png)])
    command.extend([
        "-filter_complex",
        ";\n".join(filter_parts),
        "-map",
        f"[v{len(cues)}]",
        "-map",
        "0:a?",
        "-c:v",
        "libx264",
        "-preset",
        args.preset,
        "-crf",
        str(args.crf),
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "copy",
        "-movflags",
        "+faststart",
        str(args.out),
    ])
    subprocess.run(command, check=True)
    print(f"OK {args.out}")


if __name__ == "__main__":
    try:
        main()
    except subprocess.CalledProcessError as exc:
        sys.exit(exc.returncode)
