"""Spaced and massed training in the arena, then retention tests.

One worker is one (protocol, manipulation, seed). The biological clock runs
at 1 min per robot-second, which is the compression used for the archived
table. A 72 h test is 72 min of simulated robot time and a few seconds of
wall time, because the parked robot only integrates the oscillator.
"""

from __future__ import annotations

import copy

import numpy as np

from brain.brain import make_brain
from brain.coding import pn_code
from brain.constants import CS_MINUS_HUE, CS_PLUS_HUE
from sim.arena import LX, LY, Agent, World

PROTOCOLS = {"1x": (1, 0.0), "massed": (5, 2.0), "spaced": (5, 15.0)}
MANIPULATIONS = {
    "WT": {},
    "eps0": {"eps": 0.0},
    "osc_off": {"osc_on": False},
    "no_learn": {"learn": False},
}
# Robot-seconds after training. At compression 1 these are biological minutes.
TESTS = [(60, "1h"), (180, "3h"), (1440, "24h"), (4320, "72h")]
DEFAULT_CONDITIONS = [
    (protocol, manip)
    for protocol in ("massed", "spaced")
    for manip in ("WT", "eps0", "osc_off")
]


def _preference(result) -> float:
    chosen_minus = result["n_csminus"]
    chosen_plus = result["n_csplus"]
    return 100.0 * (chosen_minus - chosen_plus) / max(1, chosen_minus + chosen_plus)


def test_agent(agent, n=20, seconds=45.0, record_first=False):
    """Frozen-brain clones. CS+ side alternates. PI > 0 means the robot avoids CS+."""
    n_plus = n_minus = n_none = 0
    trajs = []
    for k in range(n):
        clone = copy.deepcopy(agent)
        clone.rng = np.random.default_rng(int(agent.rng.integers(1 << 30)) + k)
        clone.reset_pose()
        side = 1.0 if k % 2 == 0 else -1.0
        lights = [(side * LX, LY, CS_PLUS_HUE), (-side * LX, LY, CS_MINUS_HUE)]
        record = record_first and k == 0
        result = clone.drive(
            World(lights),
            seconds,
            record=record,
            stop_on_choice=True,
        )
        if result["choice"] == 0:
            n_plus += 1
        elif result["choice"] == 1:
            n_minus += 1
        else:
            n_none += 1
        if record:
            trajs.append((side, result["traj"]))
    packed = {"n_csplus": n_plus, "n_csminus": n_minus, "n_none": n_none, "trajs": trajs}
    packed["PI"] = _preference(packed)
    return packed


def train(agent, protocol, record=False):
    """CS+ with a shock bar, then CS− without one. Gaps are robot-seconds."""
    n_cycles, gap = PROTOCOLS[protocol]
    log = []
    trajs = []
    for cycle in range(n_cycles):
        t0 = agent.brain.bio_min
        for name, hue, bar in (
            ("A", CS_PLUS_HUE, (0.0, 0.38)),
            ("B", CS_MINUS_HUE, None),
        ):
            agent.reset_pose()
            result = agent.drive(
                World([(0.0, LY, hue)], bar=bar),
                20.0,
                in_train=True,
                record=record and name == "A" and cycle == 0,
            )
            log.append((cycle, name, result["bumps"]))
            if record and name == "A" and cycle == 0:
                trajs.append(result["traj"])
        agent.brain.mb.end_cycle(t0, agent.brain.bio_min)
        if cycle < n_cycles - 1 and gap > 0.0:
            agent.brain.idle(gap)
    return log, trajs


def _kenyon_mask(brain):
    kenyon, _salience = brain.mb.kenyon(pn_code([0.5], [CS_PLUS_HUE]))
    return kenyon


def run_job(task):
    protocol, manip, seed, n_trials, tests, record = task
    options = MANIPULATIONS[manip]
    brain = make_brain(
        seed,
        eps=options.get("eps", 0.1),
        osc_on=options.get("osc_on", True),
        learn=options.get("learn", True),
        compression=1.0,
    )
    agent = Agent(brain)
    mask = _kenyon_mask(brain)
    rows = []
    extra = {}

    def record_row(label, t_after, result):
        traces = brain.traces(mask)
        rows.append(
            {
                "protocol": protocol,
                "manip": manip,
                "seed": seed,
                "test": label,
                "t_after_s": t_after,
                "PI": result["PI"],
                "n_csplus": result["n_csplus"],
                "n_csminus": result["n_csminus"],
                "n_none": result["n_none"],
                "S": traces["S"],
                "ARM": traces["ARM"],
                "LTM": traces["LTM"],
            }
        )

    naive = test_agent(agent, n=n_trials, record_first=record)
    record_row("naive", -1, naive)
    log, train_traj = train(agent, protocol, record=record)
    if record:
        extra["train"] = train_traj
        extra["naive"] = naive["trajs"]
    elapsed = 0
    bumps = [bumps for _c, name, bumps in log if name == "A"]
    for t_after, label in tests:
        agent.brain.idle(t_after - elapsed)
        elapsed = t_after
        result = test_agent(agent, n=n_trials, record_first=record and label == "72h")
        record_row(label, t_after, result)
        if record and label == "72h":
            extra["h72"] = result["trajs"]
    for row in rows:
        row["bumps"] = bumps
    return rows, extra


def run_experiment(seeds=4, trials=12, conditions=None, tests=None, workers=4, progress=True):
    conditions = DEFAULT_CONDITIONS if conditions is None else conditions
    tests = TESTS if tests is None else tests
    tasks = []
    for protocol, manip in conditions:
        for seed in range(seeds):
            record = seed == 0 and manip == "WT" and protocol in ("spaced", "massed")
            tasks.append((protocol, manip, seed, trials, tests, record))
    rows = []
    extras = {}
    if workers <= 1 or len(tasks) == 1:
        results = map(run_job, tasks)
        for task, (job_rows, extra) in zip(tasks, results):
            rows.extend(job_rows)
            if extra:
                extras[(task[0], task[1])] = extra
            if progress:
                print(f"  {task[0]} {task[1]} seed {task[2]}", flush=True)
        return rows, extras

    from concurrent.futures import ProcessPoolExecutor

    with ProcessPoolExecutor(max_workers=workers) as pool:
        for task, (job_rows, extra) in zip(tasks, pool.map(run_job, tasks)):
            rows.extend(job_rows)
            if extra:
                extras[(task[0], task[1])] = extra
            if progress:
                print(f"  {task[0]} {task[1]} seed {task[2]}", flush=True)
    return rows, extras
