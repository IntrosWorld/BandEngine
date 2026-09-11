"""Small, dependency-light audio output and mixing helpers."""
from __future__ import annotations

from pathlib import Path
import math
import struct
import wave

import numpy as np


SAMPLE_RATE = 48_000


def fit_length(audio: np.ndarray, frames: int) -> np.ndarray:
    audio = np.asarray(audio, dtype=np.float64)
    if audio.ndim == 1:
        audio = np.column_stack((audio, audio))
    if audio.ndim != 2 or audio.shape[1] != 2:
        raise ValueError("audio must be mono or Nx2 stereo")
    if len(audio) >= frames:
        return audio[:frames].copy()
    return np.pad(audio, ((0, frames - len(audio)), (0, 0)))


def write_wav(path: Path, audio: np.ndarray, sample_rate: int = SAMPLE_RATE) -> None:
    """Write stereo PCM24 without requiring a separate sound-file package."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    values = (np.clip(audio, -1, 1) * ((1 << 23) - 1)).astype(np.int32)
    raw = bytearray()
    for frame in values:
        for value in frame:
            raw += struct.pack("<i", int(value))[:3]
    with wave.open(str(path), "wb") as output:
        output.setnchannels(2)
        output.setsampwidth(3)
        output.setframerate(sample_rate)
        output.writeframes(raw)


def _active_rms(audio: np.ndarray) -> float:
    energy = np.mean(np.square(audio), axis=1)
    active = energy > 1e-8
    return float(np.sqrt(np.mean(energy[active]))) if active.any() else 0.0


def place(audio: np.ndarray, volume: float, pan: float, target_db: float) -> np.ndarray:
    """Apply score volume, equal-power pan, and conservative stem matching."""
    audio = np.asarray(audio, dtype=np.float64).copy()
    target = 10 ** (target_db / 20)
    gain = min(4.0, target / max(_active_rms(audio), 1e-9)) * max(0.0, volume) / 0.75
    pan = float(np.clip(pan, -1, 1))
    audio[:, 0] *= math.sqrt(1 - max(0.0, pan))
    audio[:, 1] *= math.sqrt(1 + min(0.0, pan))
    return audio * gain


def mix(stems: list[tuple[np.ndarray, dict]], frames: int) -> np.ndarray:
    output = np.zeros((frames, 2), dtype=np.float64)
    has_solo = any(info.get("solo") for _, info in stems)
    for audio, info in stems:
        if info.get("muted") or (has_solo and not info.get("solo")):
            continue
        family = info["family"]
        target = -23.0 if family == "drums" else -24.0 if family == "bass" else -22.0
        output += place(fit_length(audio, frames), info.get("volume", 0.75), info.get("pan", 0.0), target)
    peak = float(np.max(np.abs(output))) if output.size else 0.0
    if peak:
        output *= min(1.0, 0.92 / peak)
    return output

