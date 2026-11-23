"""Kenyon cells, three PPL1 compartments, and the S / ARM / LTM traces.

Labile trace S is written by a shock onto the eligible cells. Ongoing
dopamine forgets it. Dopamine also slows the conversion of S into ARM and,
after a spaced cycle, erases ARM. LTM is written only inside a window that
opens when the previous gap was at least ``gate`` biological minutes. ARM
and LTM inhibit each other. Massed training sets a fatigue ``phi`` that
biases the oscillator down; that state is imposed, not derived.
"""

from __future__ import annotations

import numpy as np

from brain.constants import K_ACTIVE, KC_FLOOR, MEMORY, N_CLAWS, N_COMPARTMENTS, N_KC, N_PN


class MB:
    def __init__(self, rng, gains, n_kc=N_KC, claws=N_CLAWS, k=K_ACTIVE, variant="COI", learn=True, norm=None):
        self.idx = np.stack([rng.choice(N_PN, claws, replace=False) for _ in range(n_kc)]).astype(np.uint8)
        self.n_kc = n_kc
        self.k = k
        self.jitter = rng.random(n_kc).astype(np.float32)
        self.S = np.zeros((N_COMPARTMENTS, n_kc), np.float32)
        self.A = np.zeros((N_COMPARTMENTS, n_kc), np.float32)
        self.L = np.zeros((N_COMPARTMENTS, n_kc), np.float32)
        self.eligibility = np.zeros(n_kc, np.float32)
        self.z_slow = 0.0
        self.gains = np.asarray(gains, np.float32)
        self.variant = variant
        self.learn = learn
        self.norm = norm
        self.cycle_ends: list[float] = []
        self.phi = 0.0
        self.win_until = -1.0
        self.erase_until = -1.0

    def kenyon(self, pn):
        total = float(pn[8])
        if total < KC_FLOOR:
            return np.zeros(self.n_kc, np.float32), 0.0
        coded = np.asarray(pn[:N_PN], dtype=np.float32) / total
        drive = coded[self.idx].sum(axis=1) + 1e-4 * self.jitter
        threshold = np.partition(drive, -self.k)[-self.k]
        active = (drive >= threshold).astype(np.float32)
        return active, min(1.0, total / 0.5)

    def mbon(self, kenyon):
        if float(kenyon.sum()) == 0.0:
            return np.ones(N_COMPARTMENTS, np.float32)
        weight = 1.0 - MEMORY["delta"] * np.minimum(1.0, self.S + self.A + self.L)
        return (weight @ kenyon) / float(kenyon.sum())

    def avoid(self, pn):
        kenyon, salience = self.kenyon(pn)
        drive = salience * float(self.gains @ (1.0 - self.mbon(kenyon)))
        return drive, kenyon

    def signals(self, dopamine):
        rectified = np.maximum(np.asarray(dopamine, dtype=np.float64) - 1.0, 0.0)
        norm = self.norm
        forgetting = np.array(
            [rectified[0] / norm["A101"], rectified[1] / norm["A103"], 0.0],
            np.float32,
        )
        if self.variant == "ADD":
            coincidence = (rectified[0] + rectified[1]) / 2.0 / norm["ADD"]
        else:
            coincidence = rectified[0] * rectified[1] / norm["COI"]
        return forgetting, float(coincidence)

    def us(self):
        """One shock. Eligible Kenyon cells in all three compartments are potentiated."""
        if not self.learn:
            return
        self.S += MEMORY["eta_p"] * self.eligibility[None, :] * (1.0 - self.S)

    def end_cycle(self, t_start, t_end):
        """Close one training cycle. Times are biological minutes.

        The gap is the rest before this cycle. A long gap opens an LTM window
        that starts now (so the rest *after* this cycle is when LTM is written).
        A short gap sets the massed fatigue. The first cycle has no gap.
        """
        gap = (t_start - self.cycle_ends[-1]) if self.cycle_ends else None
        self.cycle_ends.append(float(t_end))
        if gap is not None and gap >= MEMORY["gate"]:
            self.win_until = t_end + MEMORY["win"]
            self.erase_until = t_end + 15.0
        if gap is not None and gap < MEMORY["gate"]:
            self.phi = 1.0

    def step_mem(
        self,
        dt_bio,
        t_bio,
        forgetting,
        coincidence,
        in_train=False,
        kenyon=None,
        dt_robot=None,
        compression=1.0,
    ):
        # tau_e is 2 biological minutes. At compression 1 that is 2 robot
        # seconds, which is what this line used to divide by.
        if kenyon is not None and dt_robot is not None:
            comp = compression if compression > 0.0 else 1.0
            self.eligibility += (dt_robot * comp) / MEMORY["tau_e"] * (kenyon - self.eligibility)
        self.z_slow += dt_bio / MEMORY["tau_z"] * (coincidence - self.z_slow)
        arm_from_s = (
            MEMORY["kA"]
            * self.S
            / (1.0 + self.z_slow / MEMORY["th"])
            / (1.0 + self.L.mean(axis=1, keepdims=True) / MEMORY["thL"])
        )
        d_s = -(MEMORY["kS"] + MEMORY["kF"] * forgetting[:, None]) * self.S - arm_from_s
        erase = MEMORY["kE"] * self.z_slow * self.A if t_bio < self.erase_until else 0.0
        d_a = arm_from_s - MEMORY["kAd"] * self.A - erase
        if t_bio < self.win_until:
            write_l = MEMORY["kL"] * self.S * coincidence / (coincidence + MEMORY["th"])
        else:
            write_l = 0.0
        d_l = write_l - MEMORY["kLd"] * self.L
        if in_train:
            self.S -= dt_bio * arm_from_s
        else:
            self.S += dt_bio * d_s
        self.A += dt_bio * d_a
        self.L += dt_bio * d_l
        self.phi *= float(np.exp(-dt_bio / MEMORY["tau_phi"]))
