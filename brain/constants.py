"""Rates and sizes for the reduced mushroom body.

Memory rates are per biological minute. They are the ``behavior/xbehav.py``
rules with two changes made for the compressed robot: ``kL`` is 1/5 instead
of 1/20, and the spacing gate is causal (see ``MB.end_cycle``). Every one of
these numbers is an assumption. The qualitative directions follow Plaçais
2012 and Berry 2012; the values themselves were not measured.
"""

from __future__ import annotations

import numpy as np

# Biological minutes elapsed per robot-second. 1 → 1 h = 1 robot-minute.
# This is the only compression knob. The robot re-exports it as
# ``config.COMPRESSION``. The oscillator, eligibility, shock pulse and
# refractory all divide by it, so one biological minute is the same
# trajectory at every value. ``robot_seconds`` turns the protocol below
# into wall-clock seconds.
# 5 is the largest of 2, 3, 5 whose spaced and massed traces stay with the
# compression-1 run (see sim/scale_check.py). 24 biological hours is 4.8 min.
DEFAULT_COMPRESSION = 5.0

# Protocol lengths in biological minutes. At compression 1 they are the
# historical robot-second timings (20 s of colour, 15 s spaced rest, …).
PROTOCOL = dict(
    red=20.0,
    blue=20.0,
    punish_every=1.2,
    in_view=1.0,
    rest_spaced=15.0,
    rest_massed=2.0,
    rest_single=0.0,
    test=45.0,
    next_day=24.0 * 60.0,
)


def robot_seconds(bio_min: float, compression: float) -> float:
    """Wall-clock seconds for a biological duration at this compression."""
    comp = float(compression)
    if not comp > 0.0:
        comp = 1.0
    return float(bio_min) / comp

N_KC = 100
N_PN = 9
N_CLAWS = 4
K_ACTIVE = 10
N_COMPARTMENTS = 3

# γ1pedc ← PPL101/MP1, γ2α′1 ← PPL103/MV1, α′2α2 ← PPL105.
# Normalised aversive drive from the connectome readout (DESIGN.md).
GAINS = np.array([0.21, 0.46, 0.33], np.float32)

# 8 hue bins at 45° plus one brightness PN. A tenth component (sqrt brightness)
# is carried along and not read by the Kenyon cells.
HUES = np.arange(8, dtype=np.float64) * 45.0
HUE_SIGMA = 30.0
# Red is punished (CS+), blue is safe (CS−). Degrees, on the same circle as
# HUES. These are the hues passed to pn_code, not the camera measurement.
# The camera follows fly-car's fitted window (red from 322°, blue 180–220°).
# A pixel that passes that window is still coded here as 0° or 240°.
CS_PLUS_HUE = 0.0
CS_MINUS_HUE = 240.0

# Per biological minute, except eta_p (per US pulse) and the taus in minutes.
MEMORY = dict(
    kS=1 / 60,
    kF=1 / 60,
    kA=1 / 30,
    th=0.5,
    thL=0.2,
    kAd=1 / (48 * 60),
    kL=1 / 5,
    kE=1 / 5,
    kLd=1 / (7 * 24 * 60),
    delta=0.8,
    tau_z=30.0,
    win=10.0,
    gate=10.0,
    eta_p=0.13,
    tau_e=2.0,
    tau_phi=24 * 60.0,
)

# Innate cruise and learned avoidance. VMAX matches fly-car MOVE_MPS.
VMAX = 0.06
# Arena unicycle track, metres. This is fly-car's wheel spacing.
# sim/arena.py divides by it. It is not the measured chassis below.
TRACK = 0.12
# Measured chassis, metres. Rear track is the distance between the rear
# wheels (9.75 cm). Wheelbase is the rear axle to the front axle (8.0 cm).
# Nothing in the sim or the motor law reads these; the integrator keeps
# using TRACK so existing runs do not move.
CHASSIS_REAR_TRACK_M = 0.0975
CHASSIS_WHEELBASE_M = 0.08
WHEEL_BIAS = 0.35
WHEEL_APPROACH = 1.0
WHEEL_AVOID = 2.5
# Subtracted from both wheels, times the mean avoidance. The differential
# alone has a positive common mode, so equal avoidance used to command
# full forward. This term makes a strong match reverse.
WHEEL_RETREAT = 1.25
# Extra yaw, in the same dimensionless units, when avoidance is strong and
# the two eyes agree. +1 speeds the right wheel and slows the left (fly-car
# positive yaw, a left turn). Held until the eyes disagree by WHEEL_SYMM_RELEASE.
WHEEL_SPIN = 0.7
WHEEL_SYMM_MIN = 0.35
WHEEL_SYMM_RELEASE = 0.25

# Below this brightness the eye has no Kenyon-cell code.
KC_FLOOR = 0.03
SHOCK_REFRACTORY_S = 1.0
SHOCK_DRIVE = 1.5
SHOCK_DECAY = 5.0  # per robot-second, so a pulse lasts a few tenths
