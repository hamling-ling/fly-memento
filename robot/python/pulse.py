"""Metres per second to the -255..255 command the sketch expects.

The scale is fly-car's and has not been timed on this chassis. 0.20 m/s maps
to pulse 160. Commands inside the dead band are dropped: on the 2026-10-17
table, forward below 13 only twitched, and reverse needed a shift of 36
before both wheels actually turned.
"""

from __future__ import annotations

CRUISE_MPS = 0.20
CRUISE_PULSE = 160
PULSE_LIMIT = 255
FORWARD_START = 13
REVERSE_START = 36


def wheel_pulse(meters_per_second: float) -> int:
    scaled = float(meters_per_second) / CRUISE_MPS * CRUISE_PULSE
    rounded = int(round(scaled))
    if rounded > PULSE_LIMIT:
        return PULSE_LIMIT
    if rounded < -PULSE_LIMIT:
        return -PULSE_LIMIT
    return rounded


def motion_pulse(pulse: int) -> int:
    command = int(pulse)
    if command < 0:
        shifted = command - REVERSE_START
        if shifted < -PULSE_LIMIT:
            return -PULSE_LIMIT
        return shifted
    if command >= FORWARD_START:
        return command
    return 0


def wheel_pulses(v_left: float, v_right: float) -> tuple[int, int]:
    """Return ``(right, left)``, which is the order ``setMotorSpeed`` uses."""
    return motion_pulse(wheel_pulse(v_right)), motion_pulse(wheel_pulse(v_left))
