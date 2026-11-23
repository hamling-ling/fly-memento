"""Debug line for one brain step and the fixed-period log clock."""

from schedule import Next
from trace import trace_line, trace_mark


def _line(**overrides) -> str:
    fields = dict(
        red=(0.8, 0.1),
        blue=(0.0, 0.4),
        avoid=(0.12, 0.34),
        mbon_left=(0.9, 0.5, 0.7),
        mbon_right=(1.0, 0.8, 0.6),
        short_term=0.13,
        arm=0.04,
        ltm=0.02,
        phi=0.5,
        shocks=2,
        punished=True,
        wheel=(0.06, -0.02),
        pulses=(48, -36),
        cycle="cycle",
        mode="avoid",
        drive="avoid",
    )
    fields.update(overrides)
    return trace_line(**fields)


def test_trace_line_names_the_shock_the_mbon_and_the_pulses():
    text = _line()
    assert "red 0.80 0.10" in text
    assert "blue 0.00 0.40" in text
    assert "avoid L:0.120 R:0.340" in text
    assert "mbon L:0.90,0.50,0.70 R:1.00,0.80,0.60" in text
    assert "S 0.130" in text
    assert "ARM 0.040" in text
    assert "LTM 0.020" in text
    assert "phi 0.50" in text
    assert "shock 2" in text
    assert "punish yes" in text
    assert "wheel R:0.060 L:-0.020" in text
    assert "pulse R:48 L:-36" in text
    assert text.endswith("cycle avoid  drive avoid")


def test_trace_line_marks_a_step_without_a_shock():
    text = _line(punished=False)
    assert "punish no" in text
    assert "punish yes" not in text
    assert text.endswith("pulse R:48 L:-36  cycle avoid  drive avoid")


def test_trace_mark_ignores_a_trace_wiggle_under_a_thousandth():
    base = trace_mark((0.12, 0.34), (48, -36), False, "rest", "approach", 0.1001, 0.0201)
    wiggle = trace_mark((0.121, 0.344), (48, -36), False, "rest", "approach", 0.1004, 0.0204)
    jumped = trace_mark((0.12, 0.34), (0, 0), True, "cycle", "avoid", 0.2, 0.02)
    assert base == wiggle
    assert base != jumped


def test_before_the_deadline_does_not_fire():
    clock = Next(0.25, start=1.0)
    assert clock.tick(0.99) is False
    assert clock.tick(1.0) is True


def test_a_late_call_skips_the_missed_repeats():
    clock = Next(0.25, start=1.0)
    assert clock.tick(1.5) is True
    assert clock.at == 1.75
    assert clock.tick(1.5) is False
    assert clock.tick(1.75) is True
