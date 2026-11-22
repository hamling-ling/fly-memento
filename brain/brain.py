"""One brain: oscillator, memory, and the step the sim and the robot both call."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from brain.constants import (
    DEFAULT_COMPRESSION,
    GAINS,
    N_COMPARTMENTS,
    SHOCK_DECAY,
    SHOCK_DRIVE,
    SHOCK_REFRACTORY_S,
)
from brain.dan import DAN2
from brain.memory import MB
from brain.sets import NORMS, OSC_SETS
from brain.wheels import wheel_speeds


@dataclass
class Step:
    avoid_left: float
    avoid_right: float
    wheel_left: float
    wheel_right: float
    shocked: bool
    forgetting: np.ndarray
    coincidence: float


class Brain:
    def __init__(
        self,
        seed,
        osc,
        norm,
        gains=None,
        variant="COI",
        eps=0.1,
        osc_on=True,
        learn=True,
        compression=DEFAULT_COMPRESSION,
    ):
        self.rng = np.random.default_rng(seed)
        self.mb = MB(
            np.random.default_rng(int(seed) + 1000),
            GAINS if gains is None else gains,
            variant=variant,
            learn=learn,
            norm=norm,
        )
        gs, ga, tau_a, dmax = osc
        self.dan = DAN2(gs, ga, tau_a, dmax, eps=eps, osc=osc_on)
        self.dan.D = np.array([4.0, 1.0 + float(self.rng.random())], np.float32)
        self.compression = float(compression)
        self.t = 0.0
        self.us_ext = 0.0
        self.shock_pending = False
        self.last_shock = -1.0e9
        self.n_shocks = 0
        self.in_cycle = False
        self.cycle_start = 0.0
        self.eps_on = float(eps) > 0.0
        self._eps_value = float(eps) if float(eps) > 0.0 else 0.1
        self.last: Step | None = None
        self._seen = None

    @property
    def bio_min(self) -> float:
        return self.t * self.compression

    def request_shock(self) -> None:
        """Ask for a US on the next step. The 1 s refractory is applied there."""
        self.shock_pending = True

    def punish(self) -> bool:
        """Deliver the shock now. False when the refractory period has not elapsed."""
        if self.t - self.last_shock < SHOCK_REFRACTORY_S:
            self.shock_pending = False
            return False
        self.mb.us()
        self.us_ext = SHOCK_DRIVE
        self.last_shock = self.t
        self.n_shocks += 1
        self.shock_pending = False
        return True

    def set_eps(self, on: bool) -> None:
        self.eps_on = bool(on)
        self.dan.eps = self._eps_value if self.eps_on else 0.0

    def set_oscillator(self, on: bool) -> None:
        self.dan.osc = bool(on)

    def begin_cycle(self) -> None:
        self.in_cycle = True
        self.cycle_start = self.bio_min

    def end_cycle(self) -> None:
        """Close the open cycle. The gap is the rest since the previous close."""
        if not self.in_cycle:
            return
        self.mb.end_cycle(self.cycle_start, self.bio_min)
        self.in_cycle = False

    def toggle_cycle(self) -> str:
        if self.in_cycle:
            self.end_cycle()
            return "rest"
        self.begin_cycle()
        return "cycle"

    def sense(self, pn_left, pn_right):
        """Kenyon cells and wheel speeds for this view. Does not advance time."""
        avoid_left, kenyon_left = self.mb.avoid(pn_left)
        avoid_right, kenyon_right = self.mb.avoid(pn_right)
        left, right = wheel_speeds(pn_left, pn_right, avoid_left, avoid_right)
        self._seen = (pn_left, pn_right, avoid_left, avoid_right, kenyon_left, kenyon_right, left, right)
        return avoid_left, avoid_right, left, right

    def integrate(self, dt, in_train=False) -> Step:
        """Shock if one is waiting, then step the oscillator and the traces.

        Call ``sense`` first. The shock uses the eligibility left by earlier
        steps; this step's Kenyon cells update eligibility afterwards.
        """
        pn_left, pn_right, avoid_left, avoid_right, kenyon_left, kenyon_right, left, right = self._seen
        shocked = self.punish() if self.shock_pending else False
        forgetting, coincidence = self._signals(dt)
        self.mb.step_mem(
            dt * self.compression,
            self.bio_min,
            forgetting,
            coincidence,
            in_train=in_train,
            kenyon=np.maximum(kenyon_left, kenyon_right),
            dt_robot=dt,
        )
        self.t += dt
        self.last = Step(avoid_left, avoid_right, left, right, shocked, forgetting, coincidence)
        return self.last

    def step(self, pn_left, pn_right, dt, in_train=False) -> Step:
        self.sense(pn_left, pn_right)
        return self.integrate(dt, in_train=in_train)

    def idle(self, seconds, dt=0.02, sub=20) -> None:
        """Parked robot, lights off. Dopamine is averaged across ``sub`` steps."""
        block = dt * sub
        n_blocks = int(round(float(seconds) / block))
        kenyon = np.zeros(self.mb.n_kc, np.float32)
        for _ in range(n_blocks):
            self.dan.off = -0.5 * self.mb.phi
            acc_f = np.zeros(N_COMPARTMENTS, np.float64)
            acc_z = 0.0
            for _ in range(sub):
                dopamine = self.dan.step(dt, ext=self.us_ext)
                self.us_ext = max(0.0, self.us_ext - dt * SHOCK_DECAY)
                forgetting, coincidence = self.mb.signals(dopamine)
                acc_f += forgetting
                acc_z += coincidence
            acc_f /= sub
            acc_z /= sub
            self.mb.step_mem(
                block * self.compression,
                self.bio_min,
                acc_f.astype(np.float32),
                acc_z,
                kenyon=kenyon,
                dt_robot=block,
            )
            self.t += block

    def traces(self, kenyon=None) -> dict[str, float]:
        if kenyon is None:
            weight = np.ones(self.mb.n_kc, np.float32)
        else:
            weight = kenyon
            if float(weight.sum()) == 0.0:
                weight = np.ones(self.mb.n_kc, np.float32)
        mask = weight > 0
        return {
            "S": float(self.mb.S[:, mask].mean()),
            "ARM": float(self.mb.A[:, mask].mean()),
            "LTM": float(self.mb.L[:, mask].mean()),
            "phi": float(self.mb.phi),
            "bio_min": float(self.bio_min),
            "shocks": int(self.n_shocks),
        }

    def status(self) -> dict:
        traces = self.traces()
        last = self.last
        if last is None:
            mode = "wait"
            avoid = (0.0, 0.0)
            wheels = (0.0, 0.0)
        else:
            avoid = (last.avoid_left, last.avoid_right)
            wheels = (last.wheel_left, last.wheel_right)
            bright = 0.0
            if self._seen is not None:
                bright = max(float(self._seen[0][8]), float(self._seen[1][8]))
            if max(avoid) > 0.15:
                mode = "avoid"
            elif bright > 0.05:
                mode = "approach"
            else:
                mode = "wait"
        return {
            "mode": mode,
            "cycle": "cycle" if self.in_cycle else "rest",
            "bio_min": traces["bio_min"],
            "compression": self.compression,
            "eps": bool(self.eps_on),
            "osc": bool(self.dan.osc),
            "shocks": traces["shocks"],
            "S": traces["S"],
            "ARM": traces["ARM"],
            "LTM": traces["LTM"],
            "phi": traces["phi"],
            "ltm_window": self.bio_min < self.mb.win_until,
            "avoid": avoid,
            "wheels": wheels,
            "robot_s": self.t,
        }

    def state_nbytes(self) -> int:
        return (
            self.mb.S.nbytes
            + self.mb.A.nbytes
            + self.mb.L.nbytes
            + self.mb.eligibility.nbytes
            + self.mb.idx.nbytes
            + self.dan.D.nbytes
            + self.dan.a.nbytes
        )

    def _signals(self, dt):
        self.dan.off = -0.5 * self.mb.phi
        dopamine = self.dan.step(dt, ext=self.us_ext)
        self.us_ext = max(0.0, self.us_ext - dt * SHOCK_DECAY)
        return self.mb.signals(dopamine)


def make_brain(seed=0, **kwargs) -> Brain:
    """A brain on one of the packaged oscillator sets. ``seed`` selects the set."""
    index = int(seed) % len(OSC_SETS)
    return Brain(seed, OSC_SETS[index], NORMS[index], **kwargs)
