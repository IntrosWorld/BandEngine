"""Adapters from normalized Guitar Pro events to physical instrument models."""
from __future__ import annotations

import json
from pathlib import Path
import tempfile

import numpy as np

from .audio import SAMPLE_RATE, fit_length
from .engine.tools import guitar_physics
from .engine.tools.render_solo import Gesture, LeadGuitar
from .engine.bass_fea import bass_model
from .engine.drum_set_fea import drum_model


ENGINE = Path(__file__).resolve().parent / "engine"


def _events(track: dict, seconds: float) -> list[dict]:
    limited = []
    for event in track["events"]:
        if event["start"] >= seconds:
            continue
        item = dict(event)
        item["duration"] = max(0.015, min(item["duration"], seconds - item["start"]))
        limited.append(item)
    return limited


def render_guitar(track: dict, seconds: float, seed: int) -> np.ndarray:
    events = _events(track, seconds)
    if not events:
        return np.zeros((round(seconds * SAMPLE_RATE), 2))
    guitar_physics.configure_tuning(track.get("baseTuning", track["tuning"]))
    gestures = []
    for event in events:
        midi = float(event["midi"])
        target = event.get("target")
        articulation = event["articulation"]
        if articulation in {"hammer_on", "pull_off"}:
            target = midi
        if articulation == "prebend_release":
            bends = event.get("bend") or []
            if bends:
                midi += float(bends[0]["value"])
            target = float(event["midi"])
        gestures.append(Gesture(
            start=float(event["start"]), duration=float(event["duration"]), midi=midi,
            target=None if target is None else float(target), velocity=int(event["velocity"]),
            articulation=articulation, vibrato_cents=float(event.get("vibrato", 0)),
            string_index=int(event["string"]),
        ))
    renderer = LeadGuitar(SAMPLE_RATE, seed=seed, tempo_bpm=track.get("tempo", 120))
    return fit_length(renderer.render(gestures), round(seconds * SAMPLE_RATE))


def render_bass(track: dict, seconds: float, seed: int) -> np.ndarray:
    events = _events(track, seconds)
    if not events:
        return np.zeros((round(seconds * SAMPLE_RATE), 2))
    tuning = track.get("baseTuning", track["tuning"])
    bass_model.configure_tuning(tuning)
    notes = [bass_model.BassNote(
        float(event["start"]), max(0.075, float(event["duration"]) * 0.94),
        int(event["midi"]), int(event["velocity"]), int(event["string"]),
    ) for event in events]
    standard = tuning == [28, 33, 38, 43]
    if standard:
        model = json.loads((ENGINE / "bass_fea" / "bass_fea_modes.json").read_text(encoding="utf-8"))
    else:
        with tempfile.TemporaryDirectory(prefix="bandengine-bass-") as directory:
            model = bass_model.generate_model(Path(directory) / "modes.json")
    return fit_length(bass_model.render_bass(model, notes, seconds, seed=seed), round(seconds * SAMPLE_RATE))


def render_drums(track: dict, seconds: float, seed: int) -> np.ndarray:
    events = _events(track, seconds)
    if not events:
        return np.zeros((round(seconds * SAMPLE_RATE), 2))
    hits = [drum_model.DrumHit(
        float(event["start"]), event["piece"], int(event["velocity"]),
        float(event.get("openAmount", 0)),
    ) for event in events]
    model = json.loads((ENGINE / "drum_set_fea" / "drum_set_fea_modes.json").read_text(encoding="utf-8"))
    return fit_length(drum_model.render_drums(model, hits, seconds, seed=seed), round(seconds * SAMPLE_RATE))


def render_track(track: dict, seconds: float, seed: int = 1978) -> np.ndarray:
    family = track["family"]
    if family == "bass":
        return render_bass(track, seconds, seed)
    if family == "drums":
        return render_drums(track, seconds, seed)
    if family in {"electric", "acoustic"}:
        return render_guitar(track, seconds, seed)
    raise ValueError(f"unsupported instrument family: {family}")

