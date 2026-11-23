"""Colour hooks, the punish page, and one dry step of the Linux-side loop."""

import json
import urllib.request

import cv2
import numpy as np

from brain.brain import make_brain
from brain.coding import pn_code
from brain.constants import CS_MINUS_HUE, CS_PLUS_HUE, VMAX, WHEEL_BIAS
from brain.wheels import drive_name, wheel_speeds
from colors import (
    BLUE_H_HIGH,
    BLUE_H_LOW,
    FRACTION_FLOOR,
    RED_H_LOW,
    RED_H_WRAP,
    REGION_MIN_FRACTION,
    Eyes,
    _large_regions,
    eye_fractions,
    pn_from_fractions,
)
from config import EXPLORE_BIAS, WHEEL_STOP_MPS
from main import run
from motors import ListMotors
from pulse import settle_speeds, wheel_pulses
from train_ui import TrainUI


def _frame(left_bgr, right_bgr, width=64, height=24):
    image = np.zeros((height, width, 3), np.uint8)
    image[:, : width // 2] = left_bgr
    image[:, width // 2 :] = right_bgr
    return image


def _solid(bgr, width=64, height=24):
    image = np.zeros((height, width, 3), np.uint8)
    image[:] = bgr
    return image


def _bgr(hue: int, saturation: int = 255, value: int = 255) -> tuple[int, int, int]:
    """BGR for a hue in degrees. OpenCV stores half of that, so ``hue`` is even."""
    pixel = np.uint8([[[hue // 2, saturation, value]]])
    colour = cv2.cvtColor(pixel, cv2.COLOR_HSV2BGR)[0, 0]
    return int(colour[0]), int(colour[1]), int(colour[2])


# fly-car's paper. Red sits near 340°. Blue is inside 180°–220°.
PAPER_RED = _bgr(340, 220, 180)
PAPER_BLUE = _bgr(200, 220, 180)


def _owner_noise():
    return {"red_l": 0.01, "red_r": 0.03, "blue_l": 0.00, "blue_r": 0.01}


def test_flycar_gates_count_the_paper_and_not_hue_zero():
    assert RED_H_LOW == -1
    assert RED_H_WRAP == 322
    assert (BLUE_H_LOW, BLUE_H_HIGH) == (180, 220)
    assert FRACTION_FLOOR == 0.05
    # The fitted red window is the high side only. Hue 0 is not this paper.
    pure = eye_fractions(_solid(_bgr(0, 255, 255)))
    assert pure["red_l"] == 0.0
    paper = eye_fractions(_solid(PAPER_RED))
    assert paper["red_l"] == 1.0
    assert paper["blue_l"] == 0.0
    wide = np.zeros((36, 640, 3), np.uint8)
    wide[:] = PAPER_RED
    assert eye_fractions(wide)["red_r"] == 1.0
    # Hue 240 is the brain's CS− code, and it is outside fly-car's blue window.
    coded_blue = eye_fractions(_solid(_bgr(240, 255, 255)))
    assert coded_blue["blue_l"] == 0.0
    window = eye_fractions(_solid(PAPER_BLUE))
    assert window["blue_l"] == 1.0
    assert window["red_l"] == 0.0


def test_red_and_blue_land_in_the_matching_eye():
    frame = _frame(PAPER_RED, PAPER_BLUE)
    fractions = eye_fractions(frame)
    assert fractions["red_l"] > fractions["red_r"]
    assert fractions["blue_r"] > fractions["blue_l"]
    assert fractions["red_l"] > 0.5
    assert fractions["blue_r"] > 0.5
    # Eight columns, left four red: five columns sit in p <= 0.65, four of them red.
    narrow = np.zeros((4, 8, 3), np.uint8)
    narrow[:, :4] = PAPER_RED
    halves = eye_fractions(narrow)
    assert halves["red_l"] == 0.8
    assert halves["red_r"] == 0.2
    mirrored = eye_fractions(narrow, mirror=True)
    assert mirrored["red_l"] == 0.2
    assert mirrored["red_r"] == 0.8


def test_a_counted_colour_is_coded_at_the_fixed_hues():
    coded = pn_from_fractions({"red_l": 0.4, "red_r": 0.0, "blue_l": 0.0, "blue_r": 0.4})
    assert np.allclose(coded[0], pn_code([0.4, 0.0], [CS_PLUS_HUE, CS_MINUS_HUE]))
    assert np.allclose(coded[1], pn_code([0.0, 0.4], [CS_PLUS_HUE, CS_MINUS_HUE]))
    assert CS_PLUS_HUE == 0.0
    assert CS_MINUS_HUE == 240.0
    left, _right = pn_from_fractions({"red_l": 0.4, "red_r": 0.0, "blue_l": 0.0, "blue_r": 0.0})
    blank = pn_code([], [])
    # Hue 0 loads the 0° bin and, across the wrap, the 315° bin.
    assert left[0] > blank[0]
    assert left[7] > blank[7]


def test_floors_drop_gray_wood_skin_and_a_speck():
    assert eye_fractions(_solid((128, 128, 128))) == {
        "red_l": 0.0,
        "red_r": 0.0,
        "blue_l": 0.0,
        "blue_r": 0.0,
    }
    # fly-car's rejected room colours: orange screen, cream wall, skin, wood.
    for bgr in ((150, 224, 255), (124, 193, 246), (138, 149, 199), (29, 84, 137)):
        assert eye_fractions(_solid(bgr))["red_l"] == 0.0
    # Cyan at 170° is below the blue window. A book spine at 210° is inside it.
    assert eye_fractions(_solid(_bgr(170, 255, 255)))["blue_l"] == 0.0
    assert eye_fractions(_solid(_bgr(210, 180, 120)))["blue_l"] == 1.0
    # Saturation or value just under the red floors.
    assert eye_fractions(_solid(_bgr(340, 99, 180)))["red_l"] == 0.0
    assert eye_fractions(_solid(_bgr(340, 220, 119)))["red_l"] == 0.0
    assert eye_fractions(_solid(_bgr(200, 160, 70)))["blue_l"] == 1.0
    mask = np.zeros((100, 100), dtype=bool)
    mask[0:5, 0:5] = True
    mask[80, 80:84] = True
    kept = _large_regions(mask)
    assert int(kept[:5, :5].sum()) == 25
    assert int(kept[80, 80:84].sum()) == 0
    assert REGION_MIN_FRACTION * mask.size == 20


def test_green_and_yellow_are_not_conditioned_colours():
    frame = _frame((0, 200, 0), (0, 200, 200))
    fractions = eye_fractions(frame)
    assert fractions["red_l"] == 0.0
    assert fractions["blue_l"] == 0.0
    assert fractions["red_r"] == 0.0
    assert fractions["blue_r"] == 0.0


def test_owner_noise_plus_the_arena_bias_is_the_creep():
    """The board log was this pair: wheel about 0.022 / 0.025, pulse 18 / 20.

    The fractions in the log are already rounded to 0.01. Ungated, with the
    arena bias left on, they land on that pulse. The robot now gates them
    and passes bias 0, which the next test checks.
    """
    raw_l = pn_code([0.01, 0.00], [CS_PLUS_HUE, CS_MINUS_HUE])
    raw_r = pn_code([0.03, 0.01], [CS_PLUS_HUE, CS_MINUS_HUE])
    left, right = wheel_speeds(raw_l, raw_r, 0.0, 0.0)
    pulse_r, pulse_l = wheel_pulses(left, right)
    assert round(right, 3) == 0.022
    assert pulse_r == 18
    assert pulse_l >= 18


def test_noise_fractions_do_not_reach_the_brain_or_the_wheels():
    assert EXPLORE_BIAS == 0.0
    left, right = pn_from_fractions(_owner_noise())
    assert np.all(left == 0.0)
    assert np.all(right == 0.0)
    step = make_brain(0).step(left, right, 0.02, bias=EXPLORE_BIAS)
    speeds = settle_speeds(step.wheel_left, step.wheel_right, WHEEL_STOP_MPS)
    assert speeds == (0.0, 0.0)
    assert wheel_pulses(*speeds) == (0, 0)


def test_no_target_holds_the_wheels():
    dark = np.zeros(10, np.float32)
    held = wheel_speeds(dark, dark, 0.0, 0.0, bias=0.0)
    assert held == (0.0, 0.0)
    # The arena cruise is what made an empty scene pulse 17.
    creep = wheel_speeds(dark, dark, 0.0, 0.0)
    assert abs(creep[0] - WHEEL_BIAS * VMAX) < 1e-9
    assert abs(creep[1] - WHEEL_BIAS * VMAX) < 1e-9
    assert wheel_pulses(*creep) == (17, 17)
    step = make_brain(0).step(dark, dark, 0.02, bias=0.0)
    speeds = settle_speeds(step.wheel_left, step.wheel_right, WHEEL_STOP_MPS)
    assert speeds == (0.0, 0.0)
    assert wheel_pulses(*speeds) == (0, 0)


def test_a_real_target_still_approaches_and_avoids():
    # 0.2 of each eye is past the fraction floor and past the motor dead zone.
    left, right = pn_from_fractions({"red_l": 0.2, "red_r": 0.2, "blue_l": 0.0, "blue_r": 0.0})
    plain = wheel_speeds(left, right, 0.0, 0.0, bias=0.0)
    turned = wheel_speeds(left, right, 0.4, 0.0, bias=0.0)
    plain_s = settle_speeds(*plain, WHEEL_STOP_MPS)
    turned_s = settle_speeds(*turned, WHEEL_STOP_MPS)
    assert plain_s[0] > 0.0 and plain_s[1] > 0.0
    assert wheel_pulses(*plain_s) != (0, 0)
    assert turned_s[0] > plain_s[0]
    assert drive_name(left, right, 0.0, 0.0, 0.0) == "approach"
    assert drive_name(left, right, 0.4, 0.0, 0.0) == "avoid"


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


class _Clock:
    def __init__(self):
        self.t = 0.0

    def monotonic(self):
        return self.t

    def sleep(self, dt):
        self.t += float(dt)


def _drive(brain, eyes, events, duration):
    """The Linux loop, with a virtual clock and the phone buttons."""
    pending = list(events)
    phase = []

    def on_tick(elapsed):
        while pending and pending[0][0] <= elapsed + 1e-9:
            _when, action, payload = pending.pop(0)
            if action == "frame":
                eyes.frame = _solid((0, 0, 0) if payload is None else payload)
            elif action == "punish":
                brain.request_shock()
            elif action == "cycle":
                brain.toggle_cycle()
        if not phase or elapsed - phase[-1][0] >= 0.5:
            phase.append((elapsed, float(brain.dan.D[0]), float(brain.mb.L.mean()), float(brain.mb.S.mean()), float(brain.mb.A.mean()), float(brain.mb.phi)))

    run(
        brain=brain,
        eyes=eyes,
        motors=ListMotors(),
        port=0,
        duration=duration,
        dry=True,
        clock=_Clock(),
        on_tick=on_tick,
    )
    return phase


def _rounds(gap):
    """Five rounds. Red is punished, blue is shown and not punished.

    gap is None when the round button is never pressed. Otherwise it is the
    rest, in robot seconds, after 周を終えて休む.
    """
    events = []
    t = 0.0
    for _ in range(5):
        if gap is not None:
            events.append((t, "cycle", None))
        events.append((t, "frame", PAPER_RED))
        events.append((t + 1.0, "punish", None))
        events.append((t + 1.5, "frame", PAPER_BLUE))
        if gap is None:
            events.append((t + 3.0, "frame", None))
            t += 3.5
        else:
            events.append((t + 3.0, "frame", None))
            events.append((t + 3.0, "cycle", None))
            t += 3.0 + gap
    return events, t


def test_punish_outside_a_round_is_not_ignored():
    brain = make_brain(1, compression=1.0)
    page = TrainUI(brain, host="127.0.0.1", port=0).start()
    try:
        base = f"http://127.0.0.1:{page.port}"
        html = urllib.request.urlopen(base + "/", timeout=2).read().decode()
        assert "周の外でも効く" in html
        assert "赤" in html and "青" in html
        assert brain.in_cycle is False
        brain.mb.eligibility[:] = 1.0
        urllib.request.urlopen(urllib.request.Request(base + "/punish", method="POST"), timeout=2)
        brain.step(pn_code([0.5], [CS_PLUS_HUE]), pn_code([0.5], [CS_PLUS_HUE]), 0.02, in_train=brain.in_cycle)
        state = json.loads(urllib.request.urlopen(base + "/state", timeout=2).read())
    finally:
        page.close()
    assert state["cycle"] == "rest"
    assert state["rounds"] == 0
    assert state["shocks"] == 1
    assert state["S"] > 0.1
    assert state["LTM"] == 0.0
    assert "休息中でもバツは効く" in state["note"]
    assert "mp1" in state and "mv1" in state


def test_paper_red_without_a_round_writes_arm_and_not_ltm():
    # 5x (red paper 1.5 s, バツ at 1 s, blue 1.5 s). No round button.
    fill = eye_fractions(_solid(PAPER_RED))
    assert fill["red_l"] == 1.0
    assert fill["red_l"] >= FRACTION_FLOOR
    assert eye_fractions(_solid(_bgr(0, 255, 255)))["red_l"] == 0.0
    brain = make_brain(1, compression=1.0)
    events, end = _rounds(None)
    phase = _drive(brain, Eyes(), events, end + 12.0)
    status = brain.status()
    assert brain.n_shocks == 5
    assert status["cycle"] == "rest"
    assert status["mode"] == "wait"
    assert status["S"] > 0.01
    assert status["ARM"] > 0.005
    assert status["LTM"] == 0.0
    assert status["phi"] == 0.0
    assert status["shock_elig"] >= 0.05
    assert "休息中でもバツは効く" in status["note"]
    swing = max(sample[1] for sample in phase) - min(sample[1] for sample in phase)
    assert swing > 1.0


def test_spaced_red_writes_ltm_and_a_short_rest_does_not():
    spaced = make_brain(1, compression=1.0)
    spaced_events, _end = _rounds(15.0)
    early = {"ltm": None}
    pending = list(spaced_events)
    phase = []

    def on_tick(elapsed, brain=spaced, eyes=None):
        while pending and pending[0][0] <= elapsed + 1e-9:
            _when, action, payload = pending.pop(0)
            if action == "frame":
                eyes.frame = _solid((0, 0, 0) if payload is None else payload)
            elif action == "punish":
                brain.request_shock()
            elif action == "cycle":
                brain.toggle_cycle()
        # Still in the first rest: round 2 has not started, so no window yet.
        if elapsed >= 17.0 and early["ltm"] is None:
            early["ltm"] = float(brain.mb.L.mean())
        if not phase or elapsed - phase[-1][0] >= 0.5:
            phase.append((elapsed, float(brain.dan.D[0]), float(brain.mb.L.mean())))

    eyes = Eyes()
    run(
        brain=spaced,
        eyes=eyes,
        motors=ListMotors(),
        port=0,
        duration=90.0,
        dry=True,
        clock=_Clock(),
        on_tick=lambda elapsed: on_tick(elapsed, eyes=eyes),
    )
    assert early["ltm"] == 0.0
    status = spaced.status()
    assert status["rounds"] == 5
    assert status["LTM"] > 0.003
    assert status["phi"] < 0.01
    assert "長期記憶の窓" in status["note"] or status["LTM"] > 0.003
    assert max(sample[1] for sample in phase) - min(sample[1] for sample in phase) > 1.0

    massed = make_brain(1, compression=1.0)
    massed_events, massed_end = _rounds(2.0)
    _drive(massed, Eyes(), massed_events, massed_end + 1.0)
    massed_status = massed.status()
    assert massed_status["rounds"] == 5
    assert massed_status["LTM"] == 0.0
    assert massed_status["phi"] > 0.9
    assert massed_status["S"] > 0.01
    assert "疲労" in massed_status["note"]


def test_dry_loop_logs_a_shock_with_traces_and_pulses(capsys):
    brain = make_brain(0, compression=1.0)
    brain.mb.eligibility[:] = 1.0
    brain.request_shock()
    eyes = Eyes()
    eyes.frame = _solid(PAPER_RED)
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
    assert "drive " in text
    assert motors.commands[-1] == (0, 0)
    assert any(right != 0 or left != 0 for right, left in motors.commands[:-1])


def test_dry_loop_sends_wheel_commands_for_a_red_frame():
    brain = make_brain(0, compression=1.0)
    eyes = Eyes()
    eyes.frame = _solid(PAPER_RED)
    motors = ListMotors()
    run(brain=brain, eyes=eyes, motors=motors, port=0, duration=0.25, dry=True)
    assert motors.commands
    assert motors.commands[-1] == (0, 0)
    assert any(right != 0 or left != 0 for right, left in motors.commands[:-1])


def test_dry_loop_stands_still_with_no_target_and_with_noise(capsys):
    from colors import Eyes

    blank = Eyes()
    blank.frame = np.zeros((24, 64, 3), np.uint8)
    motors = ListMotors()
    run(brain=make_brain(0), eyes=blank, motors=motors, port=0, duration=0.25, dry=True)
    assert motors.commands
    assert all(command == (0, 0) for command in motors.commands)
    text = capsys.readouterr().out
    assert "wheel R:0.000 L:0.000" in text
    assert "pulse R:0 L:0" in text
    assert "drive none" in text

    # One blob the region cut keeps, still under the 0.05 eye floor.
    speck = np.zeros((50, 50, 3), np.uint8)
    speck[:8, :8] = PAPER_RED
    noisy = Eyes()
    noisy.frame = speck
    motors = ListMotors()
    run(brain=make_brain(0), eyes=noisy, motors=motors, port=0, duration=0.25, dry=True)
    assert all(command == (0, 0) for command in motors.commands)
    seen = eye_fractions(speck)
    assert 0.0 < seen["red_l"] < FRACTION_FLOOR
