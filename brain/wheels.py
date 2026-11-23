"""Crossed light approach plus ipsilateral learned avoidance.

The approach term is Braitenberg vehicle 2b, the same sign as fly-car's
DNa02 path: a bright right eye speeds the left wheel, so the robot turns
toward the light. Learned avoidance is ipsilateral and turns the robot away.
Speeds are metres per second, clipped to ``VMAX``.
"""

from __future__ import annotations

import numpy as np

from brain.constants import VMAX, WHEEL_APPROACH, WHEEL_AVOID, WHEEL_BIAS


def wheel_speeds(pn_left, pn_right, avoid_left, avoid_right, vmax=VMAX, bias=None):
    """Left and right speeds in metres per second.

    ``bias`` is the dark cruise. The arena omits it and keeps ``WHEEL_BIAS``.
    The robot passes ``EXPLORE_BIAS``, which defaults to 0: fly-car has no
    baseline drive, and 0.35 alone is already above the motor dead zone.
    """
    cruise = WHEEL_BIAS if bias is None else float(bias)
    bright_left = min(1.0, float(pn_left[8]) * 2.0)
    bright_right = min(1.0, float(pn_right[8]) * 2.0)
    avoid_left = min(1.0, float(avoid_left))
    avoid_right = min(1.0, float(avoid_right))
    left = (
        cruise
        + WHEEL_APPROACH * bright_right * (1.0 - avoid_right)
        + WHEEL_AVOID * avoid_left
        - 0.5 * WHEEL_AVOID * avoid_right
    )
    right = (
        cruise
        + WHEEL_APPROACH * bright_left * (1.0 - avoid_left)
        + WHEEL_AVOID * avoid_right
        - 0.5 * WHEEL_AVOID * avoid_left
    )
    return (
        float(np.clip(left, -1.0, 1.0) * vmax),
        float(np.clip(right, -1.0, 1.0) * vmax),
    )


def drive_name(pn_left, pn_right, avoid_left, avoid_right, bias=0.0) -> str:
    """Which term is carrying the command: explore, approach, or avoid.

    The caller prints ``none`` when the settled command is zero. Ties go to
    avoidance, then approach.
    """
    bright_left = min(1.0, float(pn_left[8]) * 2.0)
    bright_right = min(1.0, float(pn_right[8]) * 2.0)
    avoid_left = min(1.0, float(avoid_left))
    avoid_right = min(1.0, float(avoid_right))
    explore = abs(float(bias)) * 2.0
    approach = abs(WHEEL_APPROACH * bright_right * (1.0 - avoid_right)) + abs(
        WHEEL_APPROACH * bright_left * (1.0 - avoid_left)
    )
    avoid = abs(WHEEL_AVOID * avoid_left - 0.5 * WHEEL_AVOID * avoid_right) + abs(
        WHEEL_AVOID * avoid_right - 0.5 * WHEEL_AVOID * avoid_left
    )
    name = "explore"
    score = explore
    if approach > score:
        name, score = "approach", approach
    if avoid > score:
        name = "avoid"
    return name
