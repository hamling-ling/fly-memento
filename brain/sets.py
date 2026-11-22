"""Four reduced PPL101/PPL103 parameter sets.

These are not a dump of the 111 Plaçais-matching sets (that scan is not in
this repo). They were picked so the reduced oscillator matches the checks in
DESIGN.md: a period of about 5–15 s, correlation near 0.95 with ``eps=0.1``,
correlation near 0 with ``eps=0``, and a coincidence ratio C(eps=0)/C(on)
near 0.3. ``NORMS`` is the free-run mean used to scale dopamine, computed
with ``eps=0.1`` over 200 s after a 100 s burn-in.

Each entry is ``(gs, ga, tau_a, Dmax)``.
"""

from __future__ import annotations

OSC_SETS = [
    (1.6, 1.4, 2.5, 9.0),
    (1.2, 1.4, 2.5, 5.0),
    (1.2, 1.0, 2.5, 9.0),
    (2.0, 1.4, 4.0, 5.0),
]

NORMS = [
    {"A101": 2.78068, "A103": 2.895865, "ADD": 2.838273, "COI": 20.976257},
    {"A101": 0.886499, "A103": 0.922809, "ADD": 0.904654, "COI": 2.88495},
    {"A101": 2.30319, "A103": 2.407926, "ADD": 2.355558, "COI": 17.27002},
    {"A101": 1.6632, "A103": 1.719906, "ADD": 1.691553, "COI": 6.283312},
]
