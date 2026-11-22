"""UNO Q Linux side. Camera to the shared brain, brain to the motor bridge.

The phone page is served here too. A shock pressed there is applied on the
next 20 ms step, and only onto Kenyon cells that were recently active, so
the button has to be pressed while the colour is in view.

Run from a checkout, with ``brain/`` next to ``robot/``:

    python3 robot/python/main.py

On the board, open ``robot/`` as the App Lab app. The sketch drives the
wheels; this process does not.
"""

from __future__ import annotations

import os
import sys
import threading
import time
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
if (_REPO / "brain" / "__init__.py").is_file():
    sys.path.insert(0, str(_REPO))
else:
    sys.path.insert(0, str(_REPO))

import numpy as np

from brain.brain import make_brain
from colors import Eyes
from config import COLOR_GAIN, COMPRESSION, COUNT_S, MAX_CATCHUP_S, MIRROR, PORT, TICK_S
from motors import open_motors
from pulse import wheel_pulses
from train_ui import TrainUI

_DARK = np.zeros(10, np.float32)


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
    started = next_tick
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
                for _ in range(steps):
                    step = brain.step(pn_left, pn_right, TICK_S, in_train=training)
            if step is not None:
                motors.send(*wheel_pulses(step.wheel_left, step.wheel_right))
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
