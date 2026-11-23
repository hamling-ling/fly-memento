"""Biological outcome stays put when the wall clock runs faster."""

import numpy as np
import pytest

from brain.brain import make_brain
from brain.coding import pn_code
from brain.constants import CS_PLUS_HUE, DEFAULT_COMPRESSION
from brain.dan import DAN2
from brain.sets import OSC_SETS
from sim.experiment import scripted_retention


def test_compression_one_oscillator_matches_the_unscaled_step():
    """A regression pin: compression 1 must stay the pre-scaling Euler step."""
    brain = make_brain(0, compression=1.0)
    red = pn_code([0.5], [CS_PLUS_HUE])
    dark = np.zeros(10, np.float32)
    for i in range(100):
        view = red if i % 2 == 0 else dark
        brain.step(view, view, 0.02)
    assert brain.dan.D.tolist() == pytest.approx([8.969854354858398, 8.987668991088867])


def test_oscillator_period_is_stable_in_biological_time():
    gs, ga, tau_a, dmax = OSC_SETS[0]

    def intervals(compression):
        unit_dt = 0.02
        # Drive the brain so the scaling lives where the robot uses it.
        brain = make_brain(0, compression=compression)
        # Same parameter set as seed 0, which is OSC_SETS[0].
        assert brain.dan.gs[0] == pytest.approx(gs)
        dark = np.zeros(10, np.float32)
        samples = []
        bio_target = 40.0
        steps = int(round((bio_target / compression) / unit_dt))
        for _ in range(steps):
            brain.step(dark, dark, unit_dt)
            samples.append((brain.bio_min, float(brain.dan.D[0])))
        series = np.array(samples)
        centred = series[:, 1] - np.mean(series[:, 1])
        # Rising crossings of the mean, after a short burn-in.
        hits = []
        for i in range(1, len(centred)):
            if series[i, 0] < 8.0:
                continue
            if centred[i - 1] <= 0.0 < centred[i]:
                hits.append(series[i, 0])
        gaps = np.diff(hits)
        return float(np.median(gaps))

    reference = intervals(1.0)
    assert 5.0 < reference < 16.0
    for compression in (2.0, 3.0, 5.0):
        assert intervals(compression) == pytest.approx(reference, rel=0.05)
    # The bare unit, stepped at the compression-1 dt, is the same object.
    bare = DAN2(gs, ga, tau_a, dmax, eps=0.1)
    assert bare.tau == pytest.approx(0.1)


@pytest.mark.parametrize("compression", [2.0, 3.0, 5.0])
@pytest.mark.parametrize("protocol", ["spaced", "massed"])
def test_scripted_outcome_matches_compression_one(protocol, compression):
    base = scripted_retention(1, protocol, 1.0, horizons=(0.0, 60.0))
    got = scripted_retention(1, protocol, compression, horizons=(0.0, 60.0))
    for ref, row in zip(base, got):
        assert row["shocks"] == ref["shocks"] == (80 if protocol != "single" else 16)
        assert row["phi"] == pytest.approx(ref["phi"], abs=0.02)
        assert row["LTM"] == pytest.approx(ref["LTM"], abs=0.01)
        assert row["ARM"] == pytest.approx(ref["ARM"], abs=0.01)
        assert row["S"] == pytest.approx(ref["S"], abs=0.01)
        assert row["LTM_on"] == pytest.approx(ref["LTM_on"], abs=0.08)
    if protocol == "spaced":
        assert got[-1]["LTM"] > 0.05
        assert got[-1]["phi"] < 0.05
    else:
        assert got[-1]["LTM"] == 0.0
        assert got[0]["phi"] == pytest.approx(1.0)


def test_default_compression_is_the_knob_the_robot_reads():
    from config import COMPRESSION

    assert DEFAULT_COMPRESSION == 5.0
    assert COMPRESSION == DEFAULT_COMPRESSION
    brain = make_brain(0)
    assert brain.compression == 5.0
    # 24 biological hours, and the shock refractory, both follow the knob.
    assert brain.timings()["day_s"] == pytest.approx(24.0 * 60.0 / 5.0)
    assert brain.refractory_s == pytest.approx(1.0 / 5.0)
