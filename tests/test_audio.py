import numpy as np

from bandengine.audio import fit_length, mix


def test_fit_length_converts_mono_and_pads():
    result = fit_length(np.ones(3), 5)
    assert result.shape == (5, 2)
    assert np.all(result[:3] == 1)
    assert np.all(result[3:] == 0)


def test_mix_is_finite_and_peak_safe():
    audio = np.ones((32, 2)) * 0.5
    info = {"family": "guitar", "volume": 0.75, "pan": 0, "muted": False, "solo": False}
    result = mix([(audio, info), (audio, info)], 32)
    assert result.shape == (32, 2)
    assert np.isfinite(result).all()
    assert np.max(np.abs(result)) <= 0.92 + 1e-9

