import numpy as np
import pytest

from bandengine.render import render_track


@pytest.mark.parametrize(
    ("family", "tuning", "event"),
    [
        ("electric", [40, 45, 50, 55, 59, 64], {
            "start": 0.0, "duration": 0.08, "midi": 40, "target": None,
            "velocity": 90, "articulation": "pick", "vibrato": 0,
            "bend": [], "string": 0,
        }),
        ("bass", [28, 33, 38, 43], {
            "start": 0.0, "duration": 0.08, "midi": 28,
            "velocity": 90, "string": 0,
        }),
        ("drums", [], {
            "start": 0.0, "duration": 0.02, "velocity": 90,
            "piece": "kick", "openAmount": 0,
        }),
    ],
)
def test_each_engine_returns_stereo_audio(family, tuning, event):
    track = {
        "family": family, "baseTuning": tuning, "tuning": tuning,
        "tempo": 120, "events": [event],
    }
    audio = render_track(track, 0.12, seed=7)
    assert audio.shape == (5760, 2)
    assert np.isfinite(audio).all()
    assert np.max(np.abs(audio)) > 0

