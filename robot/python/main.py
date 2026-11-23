"""UNO Q Linux side. Camera to the shared brain, brain to the motor bridge.

The phone page is served here too. A shock pressed there is applied on the
next 20 ms step, and only onto Kenyon cells that were recently active, so
the button has to be pressed while the colour is in view.

Run from a checkout, with ``brain/`` next to ``robot/``:

    python3 robot/python/main.py

On the board, ``scripts/deploy_fly-memento.sh`` copies this app to
``~/ArduinoApps/fly-memento`` and puts ``brain`` in ``python/brain``.
The sketch drives the wheels; this process does not. State lines go to
stdout about once a second, and faster while the robot is moving.
"""

from __future__ import annotations

import os
import sys
import threading
import time

import bootstrap

bootstrap.install()

import numpy as np

from brain.brain import make_brain
from brain.wheels import drive_name
from colors import Eyes
from config import (
    COLOR_GAIN,
    COMPRESSION,
    COUNT_S,
    DETAIL_S,
    EXPLORE_BIAS,
    LOG_S,
    MAX_CATCHUP_S,
    MIRROR,
    PORT,
    TICK_S,
    WHEEL_STOP_MPS,
)
from motors import open_motors
from pulse import settle_speeds, wheel_pulses
from schedule import Next
from trace import trace_line, trace_mark
from train_ui import TrainUI

_DARK = np.zeros(10, np.float32)


def _mbon_triple(brain, pn) -> tuple[float, float, float]:
    """Compartment readout for one eye, before this step writes memory."""
    kenyon, _salience = brain.mb.kenyon(pn)
    values = brain.mb.mbon(kenyon)
    return (float(values[0]), float(values[1]), float(values[2]))


def _busy(step, pulses, fractions, punished, mode) -> bool:
    seen = max(
        float(fractions.get("red_l", 0.0)),
        float(fractions.get("red_r", 0.0)),
        float(fractions.get("blue_l", 0.0)),
        float(fractions.get("blue_r", 0.0)),
    )
    return bool(
        punished
        or mode != "wait"
        or pulses != (0, 0)
        or seen >= 0.05
        or max(step.avoid_left, step.avoid_right) >= 0.05
    )


def run(brain=None, eyes=None, motors=None, port=PORT, duration=None, dry=False):
    """Step until ``duration`` seconds have passed, or until interrupted."""
    brain = make_brain(0, compression=COMPRESSION) if brain is None else brain
    eyes = Eyes(mirror=MIRROR, gain=COLOR_GAIN) if eyes is None else eyes
    if motors is None:
        motors = open_motors(dry=dry or _dry_requested())
    lock = threading.Lock()
    page = TrainUI(brain, lock=lock, host="0.0.0.0", port=port).start()
    next_count = 0.0
    next_tick = time.monotonic()
    pn_left = _DARK
    pn_right = _DARK
    fractions = dict(eyes.fractions)
    started = next_tick
    next_log = Next(LOG_S, start=started)
    next_detail = Next(DETAIL_S, start=started)
    last_mark = None
    try:
        while True:
            now = time.monotonic()
            if duration is not None and now - started >= duration:
                break
            if now < next_tick:
                time.sleep(min(0.002, next_tick - now))
                continue
            if now >= next_count:
                pn_left, pn_right, fractions = eyes.read()
                with lock:
                    page.seeing = fractions
                next_count = now + COUNT_S
            late = now - next_tick
            steps = min(int(MAX_CATCHUP_S / TICK_S), max(1, int(round(late / TICK_S)) if late > TICK_S else 1))
            next_tick += steps * TICK_S
            if next_tick < now:
                next_tick = now + TICK_S
            with lock:
                training = brain.in_cycle
                step = None
                punished = False
                # Sample MBON before the step. sense() reads it before punish
                # writes S, and that is the avoid the wheels are about to use.
                mbon_left = (1.0, 1.0, 1.0)
                mbon_right = (1.0, 1.0, 1.0)
                for _ in range(steps):
                    mbon_left = _mbon_triple(brain, pn_left)
                    mbon_right = _mbon_triple(brain, pn_right)
                    step = brain.step(pn_left, pn_right, TICK_S, in_train=training, bias=EXPLORE_BIAS)
                    punished = punished or bool(step.shocked)
                status = None if step is None else brain.status()
            if step is None or status is None:
                continue
            v_left, v_right = settle_speeds(step.wheel_left, step.wheel_right, WHEEL_STOP_MPS)
            if v_left == 0.0 and v_right == 0.0:
                source = "none"
            else:
                source = drive_name(pn_left, pn_right, step.avoid_left, step.avoid_right, EXPLORE_BIAS)
            pulses = wheel_pulses(v_left, v_right)
            motors.send(*pulses)
            heartbeat = next_log.tick(now)
            detail = next_detail.tick(now)
            mark = trace_mark(
                (step.avoid_left, step.avoid_right),
                pulses,
                punished,
                status["cycle"],
                status["mode"],
                status["ARM"],
                status["LTM"],
            )
            due = heartbeat or punished or mark != last_mark
            busy = _busy(step, pulses, fractions, punished, status["mode"])
            if due or (detail and busy):
                last_mark = mark
                line = trace_line(
                    (float(fractions["red_l"]), float(fractions["red_r"])),
                    (float(fractions["blue_l"]), float(fractions["blue_r"])),
                    (step.avoid_left, step.avoid_right),
                    mbon_left,
                    mbon_right,
                    status["S"],
                    status["ARM"],
                    status["LTM"],
                    status["phi"],
                    int(status["shocks"]),
                    punished,
                    (v_right, v_left),
                    pulses,
                    status["cycle"],
                    status["mode"],
                    source,
                )
                if heartbeat:
                    line += f"  n {steps}"
                print(line, flush=True)
    except KeyboardInterrupt:
        pass
    finally:
        motors.send(0, 0)
        motors.close()
        eyes.close()
        page.close()
    return brain


def _dry_requested() -> bool:
    return os.environ.get("FLY_MEMENTO_DRY") == "1" or "--dry" in sys.argv


def _under_app_lab() -> bool:
    if os.environ.get("FLY_MEMENTO_STANDALONE") == "1":
        return False
    try:
        import arduino.app_utils  # noqa: F401
    except ImportError:
        return False
    return "--dry" not in sys.argv and os.environ.get("FLY_MEMENTO_DRY") != "1"


def main():
    if _under_app_lab():
        from arduino.app_utils import App

        App.run(user_loop=run)
        return
    run(dry=_dry_requested())


if __name__ == "__main__":
    main()
