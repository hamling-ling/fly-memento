"""The shared brain: same inputs, same state, and the MCU still fits."""

import numpy as np
import pytest

from brain.brain import make_brain
from brain.budget import flop_budget, flops_per_step, mcu_state_bytes
from brain.coding import pn_code
from brain.constants import CS_PLUS_HUE, N_KC
from brain.dan import DAN2
from brain.sets import OSC_SETS
from brain.wheels import update_avoid_spin, wheel_speeds


def _dark():
    return np.zeros(10, np.float32)


def _red():
    return pn_code([0.5], [CS_PLUS_HUE])


def _run(brain, steps=40):
    red = _red()
    dark = _dark()
    for i in range(steps):
        view = red if i % 2 == 0 else dark
        brain.step(view, view, 0.02)


def test_step_is_deterministic():
    first = make_brain(7)
    second = make_brain(7)
    _run(first)
    _run(second)
    assert np.array_equal(first.mb.S, second.mb.S)
    assert np.array_equal(first.mb.A, second.mb.A)
    assert np.array_equal(first.mb.L, second.mb.L)
    assert np.array_equal(first.dan.D, second.dan.D)
    assert first.t == pytest.approx(second.t)


def test_state_size_matches_the_mcu_budget():
    brain = make_brain(0)
    assert brain.mb.S.shape == (3, N_KC)
    assert brain.mb.S.dtype == np.float32
    assert brain.mb.idx.dtype == np.uint8
    assert mcu_state_bytes() == 4488
    assert flops_per_step() == 9558
    assert sum(flop_budget().values()) == 9558
    # Live arrays are the traces the budget counts, minus the 64-byte pad
    # and plus nothing else of substance. Claws are uint8, so they match.
    assert brain.state_nbytes() == mcu_state_bytes() - 64 - 6 * 4 + brain.dan.D.nbytes + brain.dan.a.nbytes
    assert 4000 < brain.state_nbytes() < 8192


def test_shock_writes_only_eligible_cells_and_respects_refractory():
    brain = make_brain(3)
    brain.mb.eligibility[:] = 1.0
    brain.request_shock()
    brain.step(_red(), _red(), 0.02)
    assert brain.n_shocks == 1
    assert float(brain.mb.S.mean()) == pytest.approx(0.13, abs=1e-3)
    brain.request_shock()
    brain.step(_red(), _red(), 0.02)
    assert brain.n_shocks == 1

    quiet = make_brain(3, learn=False)
    quiet.mb.eligibility[:] = 1.0
    quiet.request_shock()
    quiet.step(_red(), _red(), 0.02)
    assert quiet.n_shocks == 1
    assert float(quiet.mb.S.sum()) == 0.0


def test_compression_is_bio_minutes_per_robot_second():
    brain = make_brain(0, compression=5)
    for _ in range(50):
        brain.step(_dark(), _dark(), 0.02)
    assert brain.t == pytest.approx(1.0)
    assert brain.bio_min == pytest.approx(5.0)


def test_spacing_opens_the_ltm_window_and_massed_sets_fatigue():
    spaced = make_brain(0)
    spaced.begin_cycle()
    spaced.t = 10.0
    spaced.end_cycle()
    assert spaced.mb.win_until < 0
    spaced.t = 30.0
    spaced.begin_cycle()
    spaced.t = 40.0
    spaced.end_cycle()
    assert spaced.mb.win_until == pytest.approx(50.0)
    assert spaced.mb.phi == 0.0

    massed = make_brain(0)
    massed.begin_cycle()
    massed.t = 10.0
    massed.end_cycle()
    massed.t = 12.0
    massed.begin_cycle()
    massed.t = 20.0
    massed.end_cycle()
    assert massed.mb.phi == 1.0
    assert massed.mb.win_until < 0


def test_gap_junction_off_desynchronises_the_oscillator():
    gs, ga, tau_a, dmax = OSC_SETS[0]

    def correlation(eps):
        unit = DAN2(gs, ga, tau_a, dmax, eps=eps)
        samples = []
        for i in range(int(40 / 0.02)):
            state = unit.step(0.02)
            if i > int(15 / 0.02):
                samples.append(state.copy())
        samples = np.array(samples)
        return float(np.corrcoef(samples.T)[0, 1])

    assert correlation(0.1) > 0.8
    assert correlation(0.0) < 0.3


def test_approach_is_crossed():
    dark = _dark()
    right = _dark()
    right[8] = 0.5
    left_speed, right_speed = wheel_speeds(dark, right, 0.0, 0.0)
    assert left_speed > right_speed


def _both_bright():
    view = _dark()
    view[8] = 0.5
    return view


def test_symmetric_avoidance_backs_away_and_turns():
    view = _both_bright()
    left, right = wheel_speeds(view, view, 0.8, 0.8, bias=0.0, spin=1.0)
    assert 0.5 * (left + right) <= 0.0
    assert left != right
    # The held spin is a left turn: the right wheel is the faster one.
    assert right > left
    stored, applied = update_avoid_spin(0.0, 0.8, 0.8)
    assert (stored, applied) == (1.0, 1.0)
    # A small wobble does not flip the remembered turn.
    held, still = update_avoid_spin(stored, 0.85, 0.75)
    assert (held, still) == (1.0, 1.0)
    # A clear imbalance is left to the differential and remembered the other way.
    flipped, quiet = update_avoid_spin(held, 0.9, 0.2)
    assert (flipped, quiet) == (-1.0, 0.0)


def test_one_sided_avoidance_turns_away():
    view = _both_bright()
    # Avoidance on the right eye. The right wheel must end up faster, which
    # is a left turn, away from that eye.
    left, right = wheel_speeds(view, view, 0.1, 0.8, bias=0.0)
    assert right > left
    assert 0.5 * (left + right) < 0.06


def test_naive_red_still_approaches():
    view = _both_bright()
    left, right = wheel_speeds(view, view, 0.0, 0.0, bias=0.0)
    assert left > 0.0 and right > 0.0
    assert abs(left - right) < 1e-9
