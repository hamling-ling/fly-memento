"""Reduced PPL1 oscillator: PPL101 (MP1) and PPL103 (MV1).

Two isolated units from the research DAN model. Network input is dropped.
That was checked against the full network: masking MBON11 or shuffling the
DAN wiring left the circuit statistics unchanged at gains 1–3. PPL105 is not
a unit here; the memory layer treats it as quiet.

    tau dD = -D + logi(1 + off + ext + gs (D-1) - ga (a-1) + eps (D_other - D))
    tau_a da = -a + D

``eps`` is a diffusive coupling standing in for an MP1–MV1 gap junction.
That synapse is a working hypothesis: there is no paired recording, dye
fill, or innexin result that shows it. See docs/SUMMARY.md.

float32 state, explicit Euler. ``osc=False`` turns the intrinsic recurrence
off (gs = ga = 0) and leaves the gap term in place.
"""

from __future__ import annotations

import numpy as np


def logi(x, limit):
    scale = 1.0 - 1.0 / limit
    center = 1.0 + scale * np.log(limit - 1.0)
    return limit / (1.0 + np.exp(-(x - center) / scale))


class DAN2:
    def __init__(
        self,
        gs,
        ga,
        tau_a,
        dmax,
        tau=0.1,
        het=True,
        eps=0.1,
        osc=True,
    ):
        self.gs = np.array([gs, gs], np.float32)
        self.ga = np.array([ga, ga * (0.95 if het else 1.0)], np.float32)
        self.tau_a = np.array([tau_a, tau_a * (1.1 if het else 1.0)], np.float32)
        self.dmax = float(dmax)
        self.tau = float(tau)
        self.eps = float(eps)
        self.osc = bool(osc)
        self.D = np.array([4.0, 1.2], np.float32)
        self.a = np.ones(2, np.float32)
        self.off = 0.0

    def step(self, dt, ext=0.0, average=False):
        """Explicit Euler for ``dt`` native seconds.

        Native seconds are robot seconds at compression 1. The brain passes
        ``dt_robot * compression``, which speeds the oscillator in wall-clock
        time and leaves the biological period alone. A 50 Hz tick stays
        stable because each piece keeps ``h / tau <= 0.25`` (the compression-1
        step is 0.2). ``average`` returns the mean dopamine over those pieces
        so a coarse tick still sees the same drive. One piece, which is every
        compression-1 tick, returns ``D`` itself.
        """
        dt = float(dt)
        if dt <= 0.0:
            return self.D
        limit = 0.25 * self.tau
        n = 1 if dt <= limit else int(np.ceil(dt / limit - 1e-12))
        h = dt / n
        acc = np.zeros(2, np.float64) if average and n > 1 else None
        for _ in range(n):
            drive_s, drive_a = (self.gs, self.ga) if self.osc else (0.0 * self.gs, 0.0 * self.ga)
            gap = self.eps * (self.D[::-1] - self.D)
            target = logi(
                1.0 + self.off + ext + drive_s * (self.D - 1.0) - drive_a * (self.a - 1.0) + gap,
                self.dmax,
            )
            self.a = self.a + h / self.tau_a * (-self.a + self.D)
            self.D = (self.D + h / self.tau * (-self.D + target)).astype(np.float32)
            if acc is not None:
                acc += self.D
        if acc is not None:
            return (acc / n).astype(np.float32)
        return self.D
