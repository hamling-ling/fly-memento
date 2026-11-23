"""Automatic spaced, massed, or single training.

The human still holds the papers up. This drives the round state machine,
the on-screen prompt, and the shocks while red is actually in view.
Durations are biological minutes divided by the brain's compression.
"""

from __future__ import annotations

from brain.constants import PROTOCOL, robot_seconds

KINDS = {
    "spaced": {"rest": "rest_spaced", "label": "分散"},
    "massed": {"rest": "rest_massed", "label": "集中"},
    "single": {"rest": "rest_single", "label": "1回"},
}

PROMPTS = {
    "red": "赤を見せて",
    "blue": "青を見せて",
    "rest": "休憩中、何も見せないで",
    "test": "直後テスト。赤と青を左右に置いて",
    "next_day": "翌日まで待機。何も見せないで",
    "test_next": "翌日テスト。赤と青を左右に置いて",
    "done": "終了",
    "idle": "",
    "abort": "中断しました",
}


class ProtocolError(ValueError):
    """The requested protocol is not one this page can run."""


def phase_plan(kind: str, rounds: int, compression: float) -> list[tuple[str, float]]:
    """Phase name and robot-seconds, including the immediate and next-day tests."""
    if kind not in KINDS:
        raise ProtocolError("手順は分散、集中、1回のいずれかです。")
    if isinstance(rounds, bool) or not isinstance(rounds, int):
        raise ProtocolError("周の数は 1 から 20 です。")
    if rounds < 1 or rounds > 20:
        raise ProtocolError("周の数は 1 から 20 です。")
    red = robot_seconds(PROTOCOL["red"], compression)
    blue = robot_seconds(PROTOCOL["blue"], compression)
    rest = robot_seconds(PROTOCOL[KINDS[kind]["rest"]], compression)
    test = robot_seconds(PROTOCOL["test"], compression)
    day = robot_seconds(PROTOCOL["next_day"], compression)
    plan: list[tuple[str, float]] = []
    for index in range(rounds):
        plan.append(("red", red))
        plan.append(("blue", blue))
        if index < rounds - 1 and rest > 0.0:
            plan.append(("rest", rest))
    plan.append(("test", test))
    plan.append(("next_day", day))
    plan.append(("test_next", test))
    plan.append(("done", 0.0))
    return plan


def total_robot_s(kind: str, rounds: int, compression: float) -> dict[str, float]:
    """Wall-clock seconds for the training half and for the whole protocol."""
    plan = phase_plan(kind, rounds, compression)
    train_names = {"red", "blue", "rest"}
    train = sum(length for name, length in plan if name in train_names)
    whole = sum(length for _name, length in plan)
    day = next(length for name, length in plan if name == "next_day")
    return {"train_s": train, "total_s": whole, "day_s": day}


class AutoProtocol:
    """Tick once per brain step. ``save(brain, kind)`` runs when it finishes."""

    def __init__(self, brain, save=None):
        self.brain = brain
        self.save = save
        self.running = False
        self.kind = ""
        self.rounds = 0
        self.round_index = 0
        self.phase = "idle"
        self.left = 0.0
        self.cue = False
        self.cue_seq = 0
        self.in_view = 0.0
        self.next_punish = 0.0
        self.clock = 0.0
        self.auto_shocks = 0
        self.plan: list[tuple[str, float]] = []
        self.index = 0
        self.saved = ""
        self.error = ""

    def start(self, kind: str, rounds: int = 5, cue: bool = False, plan=None) -> None:
        if self.running:
            self.halt()
        if plan is None:
            plan = phase_plan(kind, int(rounds), self.brain.compression)
            rounds = int(rounds)
        else:
            if kind not in KINDS:
                raise ProtocolError("手順は分散、集中、1回のいずれかです。")
            plan = list(plan)
            rounds = int(rounds)
        self.kind = kind
        self.rounds = rounds
        self.plan = plan
        self.index = 0
        self.running = True
        self.cue = bool(cue)
        self.in_view = 0.0
        self.clock = 0.0
        self.auto_shocks = 0
        self.saved = ""
        self.error = ""
        self.round_index = 0
        self.phase = "idle"
        self._enter(plan[0][0], plan[0][1])

    def abort(self) -> None:
        """Stop, close an open round, and say so."""
        if not self.running and self.phase in {"idle", "abort", "done"}:
            self.running = False
            return
        if self.brain.in_cycle:
            self.brain.end_cycle()
        self.running = False
        self.plan = []
        self.left = 0.0
        self.in_view = 0.0
        self.phase = "abort"
        self.cue_seq += 1
        print(f"protocol {self.kind or '-'} -> abort", flush=True)

    def halt(self) -> None:
        """Stop the prompts without touching the brain. Used before load or reset."""
        self.running = False
        self.plan = []
        self.left = 0.0
        self.in_view = 0.0
        self.phase = "idle"

    def tick(self, dt: float, red_seen: bool) -> None:
        if not self.running:
            return
        dt = float(dt)
        if dt <= 0.0:
            return
        self.clock += dt
        if self.phase == "red":
            self._maybe_punish(dt, bool(red_seen))
        self.left -= dt
        if self.left <= 1e-8:
            self._advance()

    def status(self) -> dict:
        return {
            "running": bool(self.running),
            "kind": self.kind,
            "label": KINDS.get(self.kind, {}).get("label", ""),
            "phase": self.phase,
            "prompt": PROMPTS.get(self.phase, ""),
            "left_s": max(0.0, float(self.left)),
            "round": int(self.round_index),
            "rounds": int(self.rounds),
            "cue": bool(self.cue),
            "cue_seq": int(self.cue_seq),
            "auto_shocks": int(self.auto_shocks),
            "saved": self.saved,
            "error": self.error,
        }

    def _maybe_punish(self, dt: float, red_seen: bool) -> None:
        if not red_seen:
            self.in_view = 0.0
            return
        self.in_view += dt
        comp = self.brain.compression
        need = robot_seconds(PROTOCOL["in_view"], comp)
        interval = robot_seconds(PROTOCOL["punish_every"], comp)
        if self.in_view + 1e-6 < need:
            return
        if self.clock + 1e-9 < self.next_punish:
            return
        if self.brain.t - self.brain.last_shock + 1e-9 < self.brain.refractory_s:
            return
        self.brain.request_shock()
        self.next_punish = self.clock + interval
        self.auto_shocks += 1

    def _advance(self) -> None:
        self.index += 1
        if self.index >= len(self.plan):
            self._finish()
            return
        name, length = self.plan[self.index]
        if name == "done":
            self._finish()
            return
        self._enter(name, length)

    def _finish(self) -> None:
        if self.brain.in_cycle:
            self.brain.end_cycle()
        self.running = False
        self.phase = "done"
        self.left = 0.0
        self.cue_seq += 1
        print(
            f"protocol {self.kind} -> done rounds {self.rounds} shocks {self.auto_shocks}",
            flush=True,
        )
        if self.save is None:
            return
        try:
            self.saved = str(self.save(self.brain, self.kind))
        except Exception as exc:
            self.error = str(exc)
            print(f"protocol save failed {exc}", flush=True)

    def _enter(self, name: str, length: float) -> None:
        previous = self.phase
        if name == "red":
            # A new round. Close the previous one first so the gap is the rest
            # (or ~0 when the protocol has no rest).
            if self.brain.in_cycle:
                self.brain.end_cycle()
            self.brain.begin_cycle()
            self.round_index = 1 + sum(1 for phase, _length in self.plan[: self.index] if phase == "red")
            self.in_view = 0.0
            self.next_punish = self.clock
        elif name == "blue":
            self.in_view = 0.0
        else:
            if self.brain.in_cycle:
                self.brain.end_cycle()
            self.in_view = 0.0
        self.phase = name
        self.left = float(length)
        self.cue_seq += 1
        print(
            f"protocol {self.kind} {previous} -> {name} "
            f"round {self.round_index}/{self.rounds} left {float(length):.2f}s {PROMPTS.get(name, '')}",
            flush=True,
        )
