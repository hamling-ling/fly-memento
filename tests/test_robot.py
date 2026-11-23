"""Colour hooks, the punish page, and one dry step of the Linux-side loop."""

import json
import urllib.request

import numpy as np

from brain.brain import make_brain
from brain.coding import pn_code
from brain.constants import CS_MINUS_HUE, CS_PLUS_HUE
from colors import eye_fractions, pn_from_fractions, pn_from_frame
from main import run
from motors import ListMotors
from pulse import wheel_pulses
from train_ui import TrainUI


def _frame(left_bgr, right_bgr, width=64, height=24):
    image = np.zeros((height, width, 3), np.uint8)
    image[:, : width // 2] = left_bgr
    image[:, width // 2 :] = right_bgr
    return image


def test_red_and_blue_land_in_the_matching_eye():
    frame = _frame((0, 0, 200), (200, 0, 0))
    fractions = eye_fractions(frame)
    assert fractions["red_l"] > fractions["red_r"]
    assert fractions["blue_r"] > fractions["blue_l"]
    assert fractions["red_l"] > 0.5
    assert fractions["blue_r"] > 0.5
    left, _right, _fractions = pn_from_frame(_frame((0, 0, 200), (0, 0, 200)))
    # Hue 0 (red) loads the 0° bin and, across the wrap, the 315° bin.
    blank = pn_code([], [])
    assert left[0] > blank[0]
    assert left[7] > blank[7]


def test_red_wraps_through_zero_and_blue_is_the_safe_hue():
    # BGR (40, 0, 200) is hue 348°, the high red lobe (OpenCV hue about 174).
    wrapped = eye_fractions(_frame((40, 0, 200), (40, 0, 200)))
    assert wrapped["red_l"] == 1.0
    assert wrapped["blue_l"] == 0.0
    # Pure blue is hue 240°, inside the 200–260 gate.
    blue = eye_fractions(_frame((220, 0, 0), (220, 0, 0)))
    assert blue["blue_l"] == 1.0
    assert blue["red_l"] == 0.0
    coded = pn_from_fractions({"red_l": 0.4, "red_r": 0.0, "blue_l": 0.0, "blue_r": 0.4})
    assert np.allclose(coded[0], pn_code([0.4, 0.0], [CS_PLUS_HUE, CS_MINUS_HUE]))
    assert np.allclose(coded[1], pn_code([0.0, 0.4], [CS_PLUS_HUE, CS_MINUS_HUE]))
    assert CS_PLUS_HUE == 0.0
    assert CS_MINUS_HUE == 240.0


def test_indoor_floors_drop_gray_and_keep_a_dim_patch():
    # Washed red: saturation just under the floor of 60. Hue is still 0.
    washed = eye_fractions(_frame((153, 153, 200), (153, 153, 200)))
    assert washed["red_l"] == 0.0
    # Near-black red: value just under the floor of 50.
    dark = eye_fractions(_frame((0, 0, 49), (0, 0, 49)))
    assert dark["red_l"] == 0.0
    # Dim blue still above both floors (value 80, saturation well above 60).
    dim_blue = eye_fractions(_frame((80, 15, 15), (80, 15, 15)))
    assert dim_blue["blue_l"] == 1.0
    held = eye_fractions(_frame((0, 0, 50), (0, 0, 50)))
    assert held["red_l"] == 1.0


def test_green_and_yellow_are_not_conditioned_colours():
    frame = _frame((0, 200, 0), (0, 200, 200))
    fractions = eye_fractions(frame)
    assert fractions["red_l"] == 0.0
    assert fractions["blue_l"] == 0.0
    assert fractions["red_r"] == 0.0
    assert fractions["blue_r"] == 0.0


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
        assert "赤".encode() in page_bytes
        assert "青".encode() in page_bytes
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
        brain.step(pn_code([0.5], [CS_PLUS_HUE]), pn_code([0.5], [CS_PLUS_HUE]), 0.02, in_train=True)
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
    eyes.frame = _frame((0, 0, 180), (0, 0, 180))
    motors = ListMotors()
    run(brain=brain, eyes=eyes, motors=motors, port=0, duration=0.2, dry=True)
    text = capsys.readouterr().out
    assert brain.n_shocks == 1
    assert "punish yes" in text
    assert "red " in text
    assert "blue " in text
    assert "mbon L:" in text
    assert "ARM" in text and "LTM" in text
    assert "pulse R:" in text
    assert motors.commands[-1] == (0, 0)
    assert any(right != 0 or left != 0 for right, left in motors.commands[:-1])


def test_dry_loop_sends_wheel_commands_for_a_red_frame():
    brain = make_brain(0, compression=1.0)
    from colors import Eyes

    eyes = Eyes()
    eyes.frame = _frame((0, 0, 180), (0, 0, 180))
    motors = ListMotors()
    run(brain=brain, eyes=eyes, motors=motors, port=0, duration=0.25, dry=True)
    assert motors.commands
    assert motors.commands[-1] == (0, 0)
    assert any(right != 0 or left != 0 for right, left in motors.commands[:-1])
