"""One brain: oscillator, memory, and the step the sim and the robot both call."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from brain.constants import (
    DEFAULT_COMPRESSION,
    GAINS,
    MEMORY,
    N_COMPARTMENTS,
    PROTOCOL,
    SHOCK_DECAY,
    SHOCK_DRIVE,
    SHOCK_REFRACTORY_S,
    robot_seconds,
)
from brain.snapshot import dump, load
from brain.dan import DAN2
from brain.memory import MB
from brain.sets import NORMS, OSC_SETS
from brain.wheels import update_avoid_spin, wheel_speeds


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
        self.seed = int(seed)
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
        self.shock_elig = -1.0
        self.in_cycle = False
        self.cycle_start = 0.0
        self.eps_on = float(eps) > 0.0
        self._eps_value = float(eps) if float(eps) > 0.0 else 0.1
        self.last: Step | None = None
        self._seen = None
        self.avoid_spin = 0.0
        # Birth snapshot for 「素朴に戻す」. Taken after the wiring and the
        # initial oscillator draw, before any learning.
        self._naive = dump(self)

    @property
    def bio_min(self) -> float:
        return self.t * self.compression

    def request_shock(self) -> None:
        """Ask for a US on the next step. The 1 s refractory is applied there."""
        self.shock_pending = True

    @property
    def refractory_s(self) -> float:
        """Shock refractory in robot seconds. One biological minute at any compression."""
        return robot_seconds(SHOCK_REFRACTORY_S, self.compression)

    def punish(self) -> bool:
        """Deliver the shock now. False when the refractory period has not elapsed."""
        if self.t - self.last_shock < self.refractory_s:
            self.shock_pending = False
            return False
        self.shock_elig = float(np.max(self.mb.eligibility)) if self.mb.eligibility.size else 0.0
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

    def sense(self, pn_left, pn_right, bias=None):
        """Kenyon cells and wheel speeds for this view. Does not advance time.

        ``bias`` is forwarded to ``wheel_speeds``. ``None`` keeps the arena
        cruise ``WHEEL_BIAS``. The robot passes 0 unless exploration is on.
        """
        avoid_left, kenyon_left = self.mb.avoid(pn_left)
        avoid_right, kenyon_right = self.mb.avoid(pn_right)
        stored, applied = update_avoid_spin(self.avoid_spin, avoid_left, avoid_right)
        self.avoid_spin = stored
        left, right = wheel_speeds(
            pn_left, pn_right, avoid_left, avoid_right, bias=bias, spin=applied
        )
        self._seen = (pn_left, pn_right, avoid_left, avoid_right, kenyon_left, kenyon_right, left, right)
        return avoid_left, avoid_right, left, right

    def integrate(self, dt, in_train=False) -> Step:
        """Shock if one is waiting, then step the oscillator and the traces.

        Call ``sense`` first. The shock uses the eligibility left by earlier
        steps; this step's Kenyon cells update eligibility afterwards.
        """
        pn_left, pn_right, avoid_left, avoid_right, kenyon_left, kenyon_right, left, right = self._seen
        shocked = self.punish() if self.shock_pending else False
        # Subdivide so each Euler piece is at most one compression-1 tick
        # (0.02 biological minutes). A 50 Hz tick at compression 5 is five
        # pieces with h/tau = 0.2. A shorter arena step whose biological
        # length is already 0.02 is one piece. Compression 1 is the original
        # update.
        comp = self.compression if self.compression > 0.0 else 1.0
        bio = dt * comp
        nominal = 0.02
        n = 1 if dt <= 0.0 or bio <= nominal * (1.0 + 1e-9) else int(np.ceil(bio / nominal - 1e-12))
        h_robot = dt / n
        h_bio = bio / n
        kenyon = np.maximum(kenyon_left, kenyon_right)
        forgetting = np.zeros(N_COMPARTMENTS, np.float32)
        coincidence = 0.0
        for _ in range(n):
            forgetting, coincidence = self._signals(h_robot)
            self.mb.step_mem(
                h_bio,
                self.bio_min,
                forgetting,
                coincidence,
                in_train=in_train,
                kenyon=kenyon,
                dt_robot=h_robot,
                compression=comp,
            )
            self.t += h_robot
        self.last = Step(avoid_left, avoid_right, left, right, shocked, forgetting, coincidence)
        return self.last

    def step(self, pn_left, pn_right, dt, in_train=False, bias=None) -> Step:
        self.sense(pn_left, pn_right, bias=bias)
        return self.integrate(dt, in_train=in_train)

    def idle(self, seconds, dt=0.02, sub=20) -> None:
        """Parked robot, lights off. Dopamine is averaged across microsteps.

        ``seconds`` is robot time. Each microstep is one compression-1 tick
        (``dt`` native seconds), and the memory block is ``dt * sub``
        biological minutes. A higher compression only shortens the robot
        clock; the biological Euler step stays the one compression 1 uses.
        """
        comp = self.compression if self.compression > 0.0 else 1.0
        bio_block = dt * sub
        robot_block = bio_block / comp
        if bio_block <= 0.0:
            return
        n_blocks = int(round(float(seconds) * comp / bio_block))
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
                bio_block,
                self.bio_min,
                acc_f.astype(np.float32),
                acc_z,
                kenyon=kenyon,
                dt_robot=robot_block,
                compression=comp,
            )
            self.t += robot_block

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
        schedule = self._schedule()
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
            "ltm_window": schedule["window"],
            "rounds": schedule["rounds"],
            "rest_s": schedule["rest_s"],
            "gate_s": schedule["gate_s"],
            "win_s": schedule["win_s"],
            "win_left_s": schedule["win_left_s"],
            "gap_ready": schedule["gap_ready"],
            "timings": self.timings(),
            "mp1": float(self.dan.D[0]),
            "mv1": float(self.dan.D[1]),
            "shock_elig": float(self.shock_elig),
            "note": self.operator_note(schedule),
            "avoid": avoid,
            "wheels": wheels,
            "robot_s": self.t,
        }

    def _schedule(self) -> dict:
        """Round count and the spacing clock, in robot seconds at this compression."""
        comp = self.compression if self.compression > 0.0 else 1.0
        rounds = len(self.mb.cycle_ends)
        window = self.bio_min < self.mb.win_until
        if rounds and not self.in_cycle:
            rest_bio = self.bio_min - self.mb.cycle_ends[-1]
        else:
            rest_bio = 0.0
        win_left_bio = (self.mb.win_until - self.bio_min) if window else 0.0
        gap_bio = None
        if self.in_cycle and rounds:
            gap_bio = self.cycle_start - self.mb.cycle_ends[-1]
        return {
            "rounds": rounds,
            "window": window,
            "rest_s": rest_bio / comp,
            "gate_s": MEMORY["gate"] / comp,
            "win_s": MEMORY["win"] / comp,
            "win_left_s": win_left_bio / comp,
            "gap_ready": rest_bio >= MEMORY["gate"],
            "gap_bio": gap_bio,
        }

    def operator_note(self, schedule=None) -> str:
        """One phone-sized sentence: punish is not gated, LTM is."""
        schedule = self._schedule() if schedule is None else schedule
        gate_s = schedule["gate_s"]
        win_s = schedule["win_s"]
        rounds = schedule["rounds"]
        parts = []
        if 0.0 <= self.shock_elig < 0.05:
            parts.append("直前のバツは見ていた細胞が無く、Sは増えていない。赤を見せて押す。青は罰なし。")
        if schedule["window"]:
            parts.append(
                f"長期記憶の窓、あと{schedule['win_left_s']:.0f}秒。"
                "MP1とMV1が同時に高い瞬間にLTMが増える。"
            )
        elif self.in_cycle and rounds == 0:
            parts.append(
                f"訓練の1周目。バツはSに入り、このあいだは忘却が止まる。"
                f"終わって{gate_s:.0f}秒以上休むと、次の周の終わりにLTMの窓が開く。"
            )
        elif self.in_cycle and schedule["gap_bio"] is not None and schedule["gap_bio"] >= MEMORY["gate"]:
            parts.append(
                f"訓練の{rounds + 1}周目。この周を終えると、続く{win_s:.0f}秒でLTMが増える。"
            )
        elif self.in_cycle:
            parts.append(
                f"訓練の{rounds + 1}周目。前の休息が{gate_s:.0f}秒未満。"
                "終えると疲労φが立ち、LTMは増えない。"
            )
        elif rounds == 0:
            parts.append(
                "休息中でもバツは効く。赤ならSとARMが増え、LTMは増えない。"
                f"LTMには周を2回、あいだを{gate_s:.0f}秒以上空ける。"
            )
        elif schedule["gap_ready"]:
            parts.append(
                f"休息{schedule['rest_s']:.0f}秒、完了{rounds}周。間隔は足りている。"
                f"次の周を終えると、その後{win_s:.0f}秒でLTMが増える。"
            )
        else:
            left = max(0.0, gate_s - schedule["rest_s"])
            parts.append(
                f"休息{schedule['rest_s']:.0f}秒、完了{rounds}周。間隔まであと{left:.0f}秒。"
                "短いと疲労になり、LTMは増えない。"
            )
        return "".join(parts)

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

    def timings(self) -> dict:
        """Wall-clock seconds for the operator protocol at this compression."""
        comp = self.compression if self.compression > 0.0 else 1.0
        return {
            "compression": comp,
            "red_s": robot_seconds(PROTOCOL["red"], comp),
            "blue_s": robot_seconds(PROTOCOL["blue"], comp),
            "punish_every_s": robot_seconds(PROTOCOL["punish_every"], comp),
            "in_view_s": robot_seconds(PROTOCOL["in_view"], comp),
            "rest_spaced_s": robot_seconds(PROTOCOL["rest_spaced"], comp),
            "rest_massed_s": robot_seconds(PROTOCOL["rest_massed"], comp),
            "test_s": robot_seconds(PROTOCOL["test"], comp),
            "day_s": robot_seconds(PROTOCOL["next_day"], comp),
            "gate_s": robot_seconds(MEMORY["gate"], comp),
            "win_s": robot_seconds(MEMORY["win"], comp),
            "refractory_s": self.refractory_s,
        }

    def snapshot(self) -> dict:
        return dump(self)

    def restore(self, payload: dict) -> None:
        load(self, payload)

    def reset_naive(self) -> None:
        """Drop learning and return to the fly this process was born with."""
        load(self, self._naive)

    def _signals(self, dt):
        self.dan.off = -0.5 * self.mb.phi
        comp = self.compression if self.compression > 0.0 else 1.0
        dopamine = self.dan.step(dt * comp, ext=self.us_ext)
        self.us_ext = max(0.0, self.us_ext - dt * SHOCK_DECAY * comp)
        return self.mb.signals(dopamine)


def make_brain(seed=0, **kwargs) -> Brain:
    """A brain on one of the packaged oscillator sets. ``seed`` selects the set."""
    index = int(seed) % len(OSC_SETS)
    return Brain(seed, OSC_SETS[index], NORMS[index], **kwargs)
