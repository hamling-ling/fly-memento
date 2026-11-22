"""Crossed light approach plus ipsilateral learned avoidance.

The approach term is Braitenberg vehicle 2b, the same sign as fly-car's
DNa02 path: a bright right eye speeds the left wheel, so the robot turns
toward the light. Learned avoidance is ipsilateral and turns the robot away.
Speeds are metres per second, clipped to ``VMAX``.
"""

from __future__ import annotations

import numpy as np

from brain.constants import VMAX, WHEEL_APPROACH, WHEEL_AVOID, WHEEL_BIAS


def wheel_speeds(pn_left, pn_right, avoid_left, avoid_right, vmax=VMAX):
    bright_left = min(1.0, float(pn_left[8]) * 2.0)
    bright_right = min(1.0, float(pn_right[8]) * 2.0)
    avoid_left = min(1.0, float(avoid_left))
    avoid_right = min(1.0, float(avoid_right))
    left = (
        WHEEL_BIAS
        + WHEEL_APPROACH * bright_right * (1.0 - avoid_right)
        + WHEEL_AVOID * avoid_left
        - 0.5 * WHEEL_AVOID * avoid_right
    )
    right = (
        WHEEL_BIAS
        + WHEEL_APPROACH * bright_left * (1.0 - avoid_left)
        + WHEEL_AVOID * avoid_right
        - 0.5 * WHEEL_AVOID * avoid_left
    )
    return (
        float(np.clip(left, -1.0, 1.0) * vmax),
        float(np.clip(right, -1.0, 1.0) * vmax),
    )
