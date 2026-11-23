"""Colour hooks, the punish page, and one dry step of the Linux-side loop."""

import json
import urllib.request

import numpy as np

from brain.brain import make_brain
from brain.coding import pn_code
from colors import eye_fractions, pn_from_frame
from main import run
from motors import ListMotors
from pulse import wheel_pulses
from train_ui import TrainUI


def _frame(left_bgr, right_bgr, width=64, height=24):
    image = np.zeros((height, width, 3), np.uint8)
    image[:, : width // 2] = left_bgr
    image[:, width // 2 :] = right_bgr
    return image


def test_green_and_yellow_land_in_the_matching_eye():
    frame = _frame((0, 200, 0), (0, 200, 200))
    fractions = eye_fractions(frame)
    assert fractions["green_l"] > fractions["green_r"]
    assert fractions["yellow_r"] > fractions["yellow_l"]
    assert fractions["green_l"] > 0.5
    assert fractions["yellow_r"] > 0.5
    left, _right, _fractions = pn_from_frame(frame)
    # Hue 120 (green) loads bins at 90° and 135° more than a blank eye.
    blank = pn_code([], [])
    assert left[2] + left[3] > blank[2] + blank[3]


def test_red_is_not_a_conditioned_colour():
    frame = _frame((0, 0, 220), (0, 0, 220))
    fractions = eye_fractions(frame)
    assert fractions["green_l"] == 0.0
    assert fractions["yellow_l"] == 0.0


def test_deadband_drops_a_twitch_and_keeps_a_cruise():
    assert wheel_pulses(0.01, 0.01) == (0, 0)
    right, left = wheel_pulses(0.06, 0.06)
    assert right > 0 and left > 0
    right, left = wheel_pulses(-0.06, 0.06)
    assert right > 0 and left < 0


def test_punish_page_sets_a_shock_and_the_switches():
    brain = make_brain(1)
    page = TrainUI(brain, host="127.0.0.1", port=0).start()
    try:
        base = f"http://127.0.0.1:{page.port}"
        page_bytes = urllib.request.urlopen(base + "/", timeout=2).read()
        assert "バツ".encode() in page_bytes
        urllib.request.urlopen(urllib.request.Request(base + "/punish", method="POST"), timeout=2)
        assert brain.shock_pending
        body = json.dumps({"eps": False, "osc": False}).encode()
        urllib.request.urlopen(
            urllib.request.Request(
                base + "/flags",
                data=body,
                method="POST",
                headers={"Content-Type": "application/json"},
            ),
            timeout=2,
        )
        assert brain.dan.eps == 0.0
        assert brain.dan.osc is False
        urllib.request.urlopen(urllib.request.Request(base + "/cycle", method="POST"), timeout=2)
        assert brain.in_cycle
        state = json.loads(urllib.request.urlopen(base + "/state", timeout=2).read())
        assert state["cycle"] == "cycle"
        assert state["eps"] is False
        brain.mb.eligibility[:] = 1.0
        brain.step(pn_code([0.5], [120.0]), pn_code([0.5], [120.0]), 0.02, in_train=True)
        assert brain.n_shocks == 1
        assert float(brain.mb.S.mean()) > 0.1
    finally:
        page.close()


def test_dry_loop_logs_a_shock_with_traces_and_pulses(capsys):
    from colors import Eyes

    brain = make_brain(0, compression=1.0)
    brain.mb.eligibility[:] = 1.0
    brain.request_shock()
    eyes = Eyes()
    eyes.frame = _frame((0, 180, 0), (0, 180, 0))
    motors = ListMotors()
    run(brain=brain, eyes=eyes, motors=motors, port=0, duration=0.2, dry=True)
    text = capsys.readouterr().out
    assert brain.n_shocks == 1
    assert "punish yes" in text
    assert "mbon L:" in text
    assert "ARM" in text and "LTM" in text
    assert "pulse R:" in text
    assert motors.commands[-1] == (0, 0)
    assert any(right != 0 or left != 0 for right, left in motors.commands[:-1])


def test_dry_loop_sends_wheel_commands_for_a_green_frame():
    brain = make_brain(0, compression=1.0)
    from colors import Eyes

    eyes = Eyes()
    eyes.frame = _frame((0, 180, 0), (0, 180, 0))
    motors = ListMotors()
    run(brain=brain, eyes=eyes, motors=motors, port=0, duration=0.25, dry=True)
    assert motors.commands
    assert motors.commands[-1] == (0, 0)
    assert any(right != 0 or left != 0 for right, left in motors.commands[:-1])
