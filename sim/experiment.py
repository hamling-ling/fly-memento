"""Spaced and massed training in the arena, then retention tests.

One worker is one (protocol, manipulation, seed). Durations below are
biological minutes. Robot time is that divided by compression, and the
arena paces the body by the same factor, so the path length matches
compression 1. A 72 h test is 72 biological minutes.
"""

from __future__ import annotations

import copy

import numpy as np

from brain.brain import make_brain
from brain.coding import pn_code
from brain.constants import CS_MINUS_HUE, CS_PLUS_HUE, DEFAULT_COMPRESSION, PROTOCOL
from sim.arena import LX, LY, Agent, World

PROTOCOLS = {
    "1x": (1, PROTOCOL["rest_single"]),
    "massed": (5, PROTOCOL["rest_massed"]),
    "spaced": (5, PROTOCOL["rest_spaced"]),
}
MANIPULATIONS = {
    "WT": {},
    "eps0": {"eps": 0.0},
    "osc_off": {"osc_on": False},
    "no_learn": {"learn": False},
}
# Biological minutes after training. Robot time is these divided by compression.
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


def _pace(brain) -> float:
    comp = float(brain.compression)
    return comp if comp > 0.0 else 1.0


def test_agent(agent, n=20, seconds=None, record_first=False):
    """Frozen-brain clones. CS+ side alternates. PI > 0 means the robot avoids CS+.

    ``seconds`` is biological minutes of driving (45, the arena's choice
    window). The call is shortened by compression; the body pace puts the
    distance back.
    """
    if seconds is None:
        seconds = PROTOCOL["test"]
    pace = _pace(agent.brain)
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
            seconds / pace,
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
    """CS+ with a shock bar, then CS− without one.

    Trial length and the gap are biological minutes. Robot time is that
    divided by compression.
    """
    n_cycles, gap = PROTOCOLS[protocol]
    pace = _pace(agent.brain)
    trial = PROTOCOL["red"] / pace
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
                trial,
                in_train=True,
                record=record and name == "A" and cycle == 0,
            )
            log.append((cycle, name, result["bumps"]))
            if record and name == "A" and cycle == 0:
                trajs.append(result["traj"])
        agent.brain.mb.end_cycle(t0, agent.brain.bio_min)
        if cycle < n_cycles - 1 and gap > 0.0:
            agent.brain.idle(gap / pace)
    return log, trajs


def _kenyon_mask(brain):
    kenyon, _salience = brain.mb.kenyon(pn_code([0.5], [CS_PLUS_HUE]))
    return kenyon


def run_job(task):
    protocol, manip, seed, n_trials, tests, record, compression = task
    options = MANIPULATIONS[manip]
    brain = make_brain(
        seed,
        eps=options.get("eps", 0.1),
        osc_on=options.get("osc_on", True),
        learn=options.get("learn", True),
        compression=compression,
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
    elapsed = 0.0
    pace = _pace(brain)
    bumps = [bumps for _c, name, bumps in log if name == "A"]
    for t_after, label in tests:
        agent.brain.idle((t_after - elapsed) / pace)
        elapsed = t_after
        result = test_agent(agent, n=n_trials, record_first=record and label == "72h")
        record_row(label, t_after, result)
        if record and label == "72h":
            extra["h72"] = result["trajs"]
    for row in rows:
        row["bumps"] = bumps
    return rows, extra


def run_experiment(
    seeds=4,
    trials=12,
    conditions=None,
    tests=None,
    workers=4,
    progress=True,
    compression=None,
):
    conditions = DEFAULT_CONDITIONS if conditions is None else conditions
    tests = TESTS if tests is None else tests
    compression = DEFAULT_COMPRESSION if compression is None else float(compression)
    tasks = []
    for protocol, manip in conditions:
        for seed in range(seeds):
            record = seed == 0 and manip == "WT" and protocol in ("spaced", "massed")
            tasks.append((protocol, manip, seed, trials, tests, record, compression))
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


def scripted_retention(seed, protocol, compression, horizons=(0.0, 60.0, 1440.0, 4320.0)):
    """Hold the colour still and punish on the operator schedule.

    No arena noise, so two compressions can be compared past the path
    noise. ``horizons`` are biological minutes after the last cycle.
    Each row has the all-cell means (what the phone shows) and the means
    over the cells that answer to red.
    """
    n_cycles, gap = PROTOCOLS[protocol]
    comp = float(compression) if float(compression) > 0.0 else 1.0
    brain = make_brain(seed, compression=comp)
    red = pn_code([0.5], [CS_PLUS_HUE])
    blue = pn_code([0.5], [CS_MINUS_HUE])
    dt = 0.02
    interval = PROTOCOL["punish_every"] / comp
    first = PROTOCOL["in_view"] / comp

    def hold(view, bio_min, punish):
        steps = int(round((bio_min / comp) / dt))
        next_at = first
        for i in range(steps):
            now = i * dt
            if punish and now + 1e-8 >= next_at:
                brain.request_shock()
                next_at += interval
            brain.step(view, view, dt, in_train=True)

    for cycle in range(n_cycles):
        brain.begin_cycle()
        hold(red, PROTOCOL["red"], True)
        hold(blue, PROTOCOL["blue"], False)
        brain.end_cycle()
        if cycle < n_cycles - 1 and gap > 0.0:
            brain.idle(gap / comp)

    def take(horizon):
        masked = brain.traces(red_kenyon)
        full = brain.traces(None)
        return {
            "horizon": horizon,
            "S": full["S"],
            "ARM": full["ARM"],
            "LTM": full["LTM"],
            "S_on": masked["S"],
            "ARM_on": masked["ARM"],
            "LTM_on": masked["LTM"],
            "phi": float(brain.mb.phi),
            "shocks": int(brain.n_shocks),
            "bio_min": float(brain.bio_min),
        }

    red_kenyon, _salience = brain.mb.kenyon(red)
    rows = []
    elapsed = 0.0
    for horizon in horizons:
        if horizon > elapsed:
            brain.idle((horizon - elapsed) / comp)
            elapsed = horizon
        rows.append(take(horizon))
    return rows
