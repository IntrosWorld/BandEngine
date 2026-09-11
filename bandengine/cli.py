"""Terminal interface for the physical-modeling band engine."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys
import time

import numpy as np

from .audio import SAMPLE_RATE, mix, write_wav
from .importer import ImportFailure, list_tracks, load_track
from .render import render_track


def _slug(value: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_-]+", "-", value).strip("-") or "track"


def _family_matches(track: dict, only: str) -> bool:
    if only == "all":
        return True
    if only == "guitar":
        return track["family"] in {"electric", "acoustic"}
    return track["family"] == only


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="band-engine",
        description="Render Guitar Pro guitar, bass, and drums using physical models.",
    )
    parser.add_argument("--gp-file", "--gpfile", type=Path, required=True, help="input .gp/.gpx/.gp3/.gp4/.gp5 score")
    parser.add_argument("--out", type=Path, help="output PCM24 stereo WAV")
    parser.add_argument("--seconds", type=float, help="render only the opening number of seconds")
    parser.add_argument("--track", type=int, action="append", help="render one track index; may be repeated")
    parser.add_argument("--only", choices=("all", "guitar", "bass", "drums"), default="all")
    parser.add_argument("--stems", action="store_true", help="also write one WAV per instrument track")
    parser.add_argument("--list-tracks", action="store_true", help="show tracks and exit")
    parser.add_argument("--seed", type=int, default=1978, help="deterministic performance seed")
    return parser


def _print_tracks(catalog: dict) -> None:
    print(f"{catalog['title']} ({catalog['duration']:.2f} s)")
    for track in catalog["tracks"]:
        state = "ready" if track["supported"] else f"skip: {track['reason']}"
        print(f"[{track['index']:>2}] {track['name']} | {track['family']} | {track['tone']} | {state}")


def run(args: argparse.Namespace) -> dict:
    source = args.gp_file.expanduser().resolve()
    catalog = list_tracks(source)
    if args.list_tracks:
        _print_tracks(catalog)
        return {"listed": True, "source": str(source)}
    duration = float(catalog["duration"])
    if args.seconds is not None:
        if not 0 < args.seconds <= 3600:
            raise ValueError("--seconds must be greater than zero and at most 3600")
        duration = min(duration, args.seconds)
    if not 0 < duration <= 3600:
        raise ValueError("the selected render duration must be between 0 and 3600 seconds")
    requested = set(args.track or [])
    choices = [track for track in catalog["tracks"] if track["supported"]]
    if requested:
        choices = [track for track in choices if track["index"] in requested]
        missing = requested - {track["index"] for track in choices}
        if missing:
            raise ValueError(f"unsupported or missing track index: {', '.join(map(str, sorted(missing)))}")
    choices = [track for track in choices if _family_matches(track, args.only)]
    if not choices:
        raise ValueError(f"no playable {args.only} tracks were found")

    output = (args.out or source.with_name(f"{source.stem}_band.wav")).expanduser().resolve()
    frames = round(duration * SAMPLE_RATE)
    stems = []
    report_tracks = []
    started = time.perf_counter()
    for position, choice in enumerate(choices, 1):
        print(f"[{position}/{len(choices)}] Rendering {choice['name']} ({choice['family']})...", flush=True)
        score = load_track(source, choice["index"])
        audio = render_track(score, duration, args.seed + choice["index"] * 101)
        info = {**choice, "family": score["family"]}
        stems.append((audio, info))
        stem_path = None
        if args.stems:
            stem_path = output.parent / f"{output.stem}_stems" / f"{choice['index']:02d}-{_slug(choice['name'])}.wav"
            write_wav(stem_path, audio)
        report_tracks.append({
            "index": choice["index"], "name": choice["name"], "family": score["family"],
            "tone": "distortion" if score["family"] in {"electric", "acoustic"} else score["family"],
            "events": len([event for event in score["events"] if event["start"] < duration]),
            "stem": str(stem_path) if stem_path else None,
            "warnings": score.get("warnings", []),
        })
    mixed = mix(stems, frames)
    write_wav(output, mixed)
    report = {
        "source": str(source), "output": str(output), "sample_rate": SAMPLE_RATE,
        "format": "PCM24 stereo WAV", "duration_seconds": duration,
        "elapsed_seconds": round(time.perf_counter() - started, 3),
        "method": "modal physical models; no recorded instrument samples",
        "tracks": report_tracks,
    }
    report_path = output.with_suffix(".json")
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"Wrote {output}")
    print(f"Report {report_path}")
    return report


def main(argv: list[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    try:
        run(args)
        return 0
    except (ImportFailure, ValueError, OSError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
