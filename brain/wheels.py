"""Crossed light approach plus repulsive learned avoidance.

The approach term is Braitenberg vehicle 2b, the same sign as fly-car's
DNa02 path: a bright right eye speeds the left wheel, so the robot turns
toward the light. Learned avoidance is ipsilateral and turns the robot away
from the stronger eye.

The ipsilateral pair used to keep a positive common mode, so equal avoidance
on both eyes commanded full forward and the robot drove into a centred
colour. That common mode is removed. A retreat term then slows, and at
strong avoidance reverses, both wheels. When the two eyes agree, an extra
yaw is held so the robot spins off the colour instead of dithering. fly-car
stops both wheels when red fills the frame (``RED_FILL``); here the learned
match backs away and turns. Positive speed is forward. Negative pulses are
reverse, the same sign fly-car sends to the sketch.

Speeds are metres per second, clipped to ``VMAX``.
"""

from __future__ import annotations

import numpy as np

from brain.constants import (
    VMAX,
    WHEEL_APPROACH,
    WHEEL_AVOID,
    WHEEL_BIAS,
    WHEEL_RETREAT,
    WHEEL_SPIN,
    WHEEL_SYMM_MIN,
    WHEEL_SYMM_RELEASE,
)


def _unit(value: float) -> float:
    return min(1.0, max(0.0, float(value)))


def _bright(pn) -> float:
    return min(1.0, max(0.0, float(pn[8]) * 2.0))


def update_avoid_spin(previous: float, avoid_left: float, avoid_right: float) -> tuple[float, float]:
    """Remember a turn and say whether to apply it on this step.

    Returns ``(stored, applied)``. ``applied`` is -1, 0, or +1. +1 speeds the
    right wheel. A clear imbalance (``|right - left| >= WHEEL_SYMM_RELEASE``)
    is left to the differential and only stored. Inside that band, and only
    while the mean avoidance is at least ``WHEEL_SYMM_MIN``, the stored turn
    is applied. The first choice, when nothing is stored, is +1 (a left
    turn). A small wobble does not flip it.
    """
    left = _unit(avoid_left)
    right = _unit(avoid_right)
    mean = 0.5 * (left + right)
    if mean < WHEEL_SYMM_MIN:
        return 0.0, 0.0
    difference = right - left
    if abs(difference) >= WHEEL_SYMM_RELEASE:
        return (1.0 if difference > 0.0 else -1.0), 0.0
    stored = float(previous) if float(previous) != 0.0 else (1.0 if difference >= 0.0 else -1.0)
    return stored, stored


def _commands(pn_left, pn_right, avoid_left, avoid_right, bias, spin):
    cruise = WHEEL_BIAS if bias is None else float(bias)
    bright_left = _bright(pn_left)
    bright_right = _bright(pn_right)
    left_avoid = _unit(avoid_left)
    right_avoid = _unit(avoid_right)
    approach_left = WHEEL_APPROACH * bright_right * (1.0 - right_avoid)
    approach_right = WHEEL_APPROACH * bright_left * (1.0 - left_avoid)
    # Ipsilateral speed-up and a half-size contralateral brake. The shared
    # part of that pair is forward; take it out so a centred colour does not
    # charge.
    raw_left = WHEEL_AVOID * left_avoid - 0.5 * WHEEL_AVOID * right_avoid
    raw_right = WHEEL_AVOID * right_avoid - 0.5 * WHEEL_AVOID * left_avoid
    common = 0.5 * (raw_left + raw_right)
    retreat = WHEEL_RETREAT * 0.5 * (left_avoid + right_avoid)
    yaw = WHEEL_SPIN * float(spin)
    left = cruise + approach_left + (raw_left - common) - retreat - yaw
    right = cruise + approach_right + (raw_right - common) - retreat + yaw
    return left, right, abs(approach_left) + abs(approach_right), abs(raw_left - common) + abs(raw_right - common) + 2.0 * retreat + 2.0 * abs(yaw), abs(cruise) * 2.0


def wheel_speeds(pn_left, pn_right, avoid_left, avoid_right, vmax=VMAX, bias=None, spin=0.0):
    """Left and right speeds in metres per second.

    ``bias`` is the dark cruise. The arena omits it and keeps ``WHEEL_BIAS``.
    The robot passes ``EXPLORE_BIAS``, which defaults to 0. ``spin`` is the
    held symmetric-avoidance turn from ``update_avoid_spin`` (-1, 0, or +1).
    """
    left, right, _approach, _avoid, _explore = _commands(pn_left, pn_right, avoid_left, avoid_right, bias, spin)
    return (
        float(np.clip(left, -1.0, 1.0) * vmax),
        float(np.clip(right, -1.0, 1.0) * vmax),
    )


def drive_name(pn_left, pn_right, avoid_left, avoid_right, bias=0.0, spin=0.0) -> str:
    """Which term is carrying the command: explore, approach, or avoid.

    The caller prints ``none`` when the settled command is zero. Ties go to
    avoidance, then approach. Retreat and the held spin count as avoidance,
    so a centred punished colour is not labelled as approach.
    """
    _left, _right, approach, avoid, explore = _commands(
        pn_left, pn_right, avoid_left, avoid_right, bias, spin
    )
    name = "explore"
    score = explore
    if approach > score:
        name, score = "approach", approach
    if avoid > score:
        name = "avoid"
    return name
