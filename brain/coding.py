"""Colour and brightness to nine projection-neuron rates, per eye."""

from __future__ import annotations

import numpy as np

from brain.constants import HUE_SIGMA, HUES


def pn_code(intensity, hue) -> np.ndarray:
    """Return 10 PN rates: 8 hue bins, total brightness, sqrt brightness.

    ``intensity`` and ``hue`` are one entry per visible lamp (or per colour
    the camera counted). An empty scene is all zeros. The Kenyon cells read
    the first nine entries; the last is unused and kept so old traces match.
    """
    weights = np.asarray(intensity, dtype=np.float64).reshape(-1)
    hues = np.asarray(hue, dtype=np.float64).reshape(-1)
    if weights.size == 0:
        return np.zeros(10, np.float32)
    delta = np.abs(((HUES[None, :] - hues[:, None]) + 180.0) % 360.0 - 180.0)
    bins = (weights[:, None] * np.exp(-(delta**2) / (2.0 * HUE_SIGMA**2))).sum(axis=0)
    total = float(weights.sum())
    return np.concatenate([bins, [total, np.sqrt(max(total, 0.0))]]).astype(np.float32)
