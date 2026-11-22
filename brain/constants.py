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
DEFAULT_COMPRESSION = 1.0

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
CS_PLUS_HUE = 120.0  # green
CS_MINUS_HUE = 60.0  # yellow

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

# Below this brightness the eye has no Kenyon-cell code.
KC_FLOOR = 0.03
SHOCK_REFRACTORY_S = 1.0
SHOCK_DRIVE = 1.5
SHOCK_DECAY = 5.0  # per robot-second, so a pulse lasts a few tenths
