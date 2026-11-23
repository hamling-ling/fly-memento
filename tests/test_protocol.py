"""The automatic training state machine, with simulated colour detections."""

import json
import urllib.error
import urllib.request

import numpy as np
import pytest

from brain.brain import make_brain
from brain.coding import pn_code
from brain.constants import CS_MINUS_HUE, CS_PLUS_HUE, DEFAULT_COMPRESSION
from colors import Eyes
from main import run
from motors import ListMotors
from protocol import PROMPTS, AutoProtocol, phase_plan, total_robot_s
from test_robot import PAPER_RED, _Clock, _solid
from train_ui import TrainUI


def _views():
    red = pn_code([0.5], [CS_PLUS_HUE])
    blue = pn_code([0.5], [CS_MINUS_HUE])
    dark = np.zeros(10, np.float32)
    return red, blue, dark


def _drive(proto, brain, seconds, seen, view):
    dt = 0.02
    steps = int(round(seconds / dt))
    for _ in range(steps):
        proto.tick(dt, seen)
        brain.step(view, view, dt, in_train=brain.in_cycle)
    return steps


def test_plan_uses_the_compression_knob():
    assert PROMPTS["red"] == "赤を見せて"
    assert PROMPTS["blue"] == "青を見せて"
    assert PROMPTS["rest"] == "休憩中、何も見せないで"
    assert PROMPTS["done"] == "終了"
    comp = DEFAULT_COMPRESSION
    plan = phase_plan("spaced", 5, comp)
    assert [name for name, _length in plan[:3]] == ["red", "blue", "rest"]
    assert plan[-4][0] == "test"
    assert plan[-3][0] == "next_day"
    assert plan[-2][0] == "test_next"
    assert plan[-1] == ("done", 0.0)
    assert plan[0][1] == pytest.approx(20.0 / comp)
    assert plan[2][1] == pytest.approx(15.0 / comp)
    assert plan[-3][1] == pytest.approx(24.0 * 60.0 / comp)
    massed = phase_plan("massed", 5, comp)
    assert massed[2][1] == pytest.approx(2.0 / comp)
    single = phase_plan("single", 1, comp)
    assert [name for name, _length in single] == ["red", "blue", "test", "next_day", "test_next", "done"]
    totals = total_robot_s("spaced", 5, comp)
    assert totals["train_s"] == pytest.approx(5 * (20.0 + 20.0) / comp + 4 * 15.0 / comp)
    assert totals["day_s"] == pytest.approx(1440.0 / comp)
    assert totals["total_s"] == pytest.approx(totals["train_s"] + totals["day_s"] + 2 * 45.0 / comp)
    with pytest.raises(ValueError, match="手順"):
        phase_plan("nope", 5, comp)
    with pytest.raises(ValueError, match="周"):
        phase_plan("spaced", 0, comp)


def test_auto_punish_needs_red_in_view_and_skips_blue(capsys):
    brain = make_brain(1, compression=1.0)
    red, blue, dark = _views()
    saved = []
    proto = AutoProtocol(brain, save=lambda _brain, kind: saved.append(kind) or "kept")
    # Short phases, but the 1 s in-view rule and the 1.2 s rate are the real ones.
    proto.start(
        "spaced",
        rounds=2,
        cue=False,
        plan=[
            ("red", 3.0),
            ("blue", 1.0),
            ("rest", 0.5),
            ("red", 2.0),
            ("blue", 0.5),
            ("test", 0.2),
            ("next_day", 0.2),
            ("test_next", 0.2),
            ("done", 0.0),
        ],
    )
    assert proto.status()["prompt"] == "赤を見せて"
    assert brain.in_cycle is True
    # Half a second of red is not enough.
    _drive(proto, brain, 0.5, True, red)
    assert brain.n_shocks == 0
    assert proto.phase == "red"
    # Look away, then the in-view clock starts over.
    _drive(proto, brain, 0.3, False, dark)
    _drive(proto, brain, 0.8, True, red)
    assert brain.n_shocks == 0
    _drive(proto, brain, 0.3, True, red)
    assert brain.n_shocks == 1
    # The next one is due 1.2 s later, which lands on the last tick of this
    # 3 s red phase. It still counts; the phase then closes.
    _drive(proto, brain, 1.1, True, red)
    assert brain.n_shocks == 2
    assert proto.phase == "blue"
    assert proto.status()["prompt"] == "青を見せて"
    # Red paper during the blue phase must not be punished by the protocol.
    _drive(proto, brain, 1.0, True, red)
    assert brain.n_shocks == 2
    assert proto.phase == "rest"
    assert proto.status()["prompt"] == "休憩中、何も見せないで"
    assert brain.in_cycle is False
    _drive(proto, brain, 0.5, False, dark)
    assert proto.phase == "red"
    assert proto.status()["round"] == 2
    # Second round is 2 s. One shock after 1 s; the next rate slot is past the end.
    _drive(proto, brain, 2.0, True, red)
    assert brain.n_shocks == 3
    assert proto.phase == "blue"
    _drive(proto, brain, 0.5, False, blue)
    assert proto.phase == "test"
    assert "直後テスト" in proto.status()["prompt"]
    _drive(proto, brain, 0.2, False, dark)
    assert proto.phase == "next_day"
    assert "何も見せないで" in proto.status()["prompt"]
    _drive(proto, brain, 0.2, False, dark)
    assert proto.phase == "test_next"
    _drive(proto, brain, 0.2, False, dark)
    assert proto.phase == "done"
    assert proto.status()["prompt"] == "終了"
    assert proto.running is False
    assert saved == ["spaced"]
    text = capsys.readouterr().out
    assert "protocol spaced idle -> red" in text
    assert "protocol spaced red -> blue" in text
    assert "protocol spaced -> done" in text
    # The manual button still delivers a shock after the protocol has finished.
    brain.mb.eligibility[:] = 1.0
    brain.request_shock()
    brain.step(red, red, 0.02)
    assert brain.n_shocks == 4


def test_abort_closes_the_round_and_stops_the_shocks():
    brain = make_brain(1, compression=1.0)
    red, _blue, _dark = _views()
    proto = AutoProtocol(brain)
    proto.start("massed", rounds=5, cue=True)
    _drive(proto, brain, 1.2, True, red)
    assert brain.n_shocks >= 1
    assert brain.in_cycle is True
    proto.abort()
    assert proto.phase == "abort"
    assert proto.status()["prompt"] == "中断しました"
    assert brain.in_cycle is False
    shocks = brain.n_shocks
    _drive(proto, brain, 2.0, True, red)
    assert brain.n_shocks == shocks


def test_refractory_blocks_an_auto_shock_that_is_otherwise_due():
    brain = make_brain(1, compression=1.0)
    proto = AutoProtocol(brain)
    proto.phase = "red"
    proto.running = True
    proto.in_view = 2.0
    proto.clock = 5.0
    proto.next_punish = 0.0
    brain.last_shock = brain.t
    proto._maybe_punish(0.02, True)
    assert brain.shock_pending is False
    assert proto.auto_shocks == 0


def test_page_starts_and_aborts_and_the_manual_buttons_remain(capsys):
    brain = make_brain(1, compression=DEFAULT_COMPRESSION)
    page = TrainUI(brain, host="127.0.0.1", port=0).start()
    try:
        base = f"http://127.0.0.1:{page.port}"
        started = _post(base + "/protocol/start", {"protocol": "single", "rounds": 1, "cue": False})
        assert started["ok"] is True
        assert started["protocol"]["prompt"] == "赤を見せて"
        assert brain.in_cycle is True
        # Manual バツ and 周 still hit the brain while the protocol is running.
        urllib.request.urlopen(urllib.request.Request(base + "/punish", method="POST"), timeout=2)
        assert brain.shock_pending is True
        urllib.request.urlopen(urllib.request.Request(base + "/cycle", method="POST"), timeout=2)
        assert brain.in_cycle is False
        state = json.loads(urllib.request.urlopen(base + "/state", timeout=2).read())
        assert state["protocol"]["running"] is True
        assert "timings" in state
        assert state["timings"]["day_s"] == pytest.approx(1440.0 / DEFAULT_COMPRESSION)
        aborted = _post(base + "/protocol/abort", {})
        assert aborted["protocol"]["phase"] == "abort"
        bad = _post(base + "/protocol/start", {"protocol": "weekly", "rounds": 5})
        assert bad["ok"] is False
        assert "手順" in bad["error"]
    finally:
        page.close()
    text = capsys.readouterr().out
    assert "protocol single" in text
    assert "-> abort" in text


def test_robot_loop_punishes_a_red_frame_without_the_button(tmp_path, monkeypatch):
    monkeypatch.setenv("FLY_MEMENTO_DATA", str(tmp_path))
    brain = make_brain(1, compression=DEFAULT_COMPRESSION)
    page = TrainUI(brain, host="127.0.0.1", port=0)
    page.protocol.start("spaced", rounds=1, cue=False)
    eyes = Eyes()
    eyes.frame = _solid(PAPER_RED)
    # One robot second. In-view gate is 1/compression seconds, then every
    # 1.2/compression seconds, and the red phase is 20/compression seconds.
    try:
        run(
            brain=brain,
            eyes=eyes,
            motors=ListMotors(),
            page=page,
            duration=1.0,
            dry=True,
            clock=_Clock(),
        )
    finally:
        page.close()
    comp = DEFAULT_COMPRESSION
    first = 1.0 / comp
    interval = 1.2 / comp
    expected = 0
    t = first
    while t <= 1.0 + 1e-9:
        expected += 1
        t += interval
    assert brain.n_shocks == expected
    assert brain.n_shocks >= 1
    assert float(brain.mb.S.mean()) > 0.0


def _post(url, payload):
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode(),
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    try:
        response = urllib.request.urlopen(request, timeout=2)
    except urllib.error.HTTPError as exc:
        response = exc
    with response:
        return json.loads(response.read().decode())
