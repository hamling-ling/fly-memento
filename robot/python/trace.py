"""One debug line for the brain and the wheel command.

The 1 Hz line is the idle heartbeat. A punish, a new pulse, or a new
mode is printed as soon as it happens. ``wheel`` and the pulses are
right, then left, which is the order ``setMotorSpeed`` uses.
``drive`` names the term that survived the stop floor: ``explore``,
``approach``, ``avoid``, or ``none``.
"""

from __future__ import annotations


def trace_line(
    red: tuple[float, float],
    blue: tuple[float, float],
    avoid: tuple[float, float],
    mbon_left: tuple[float, float, float],
    mbon_right: tuple[float, float, float],
    short_term: float,
    arm: float,
    ltm: float,
    phi: float,
    shocks: int,
    punished: bool,
    wheel: tuple[float, float],
    pulses: tuple[int, int],
    cycle: str,
    mode: str,
    drive: str = "none",
) -> str:
    """Format one step. MBON values are the three compartments, left eye then right."""
    flag = "yes" if punished else "no"
    right_v, left_v = wheel
    pulse_r, pulse_l = pulses
    return (
        f"red {red[0]:.2f} {red[1]:.2f}  "
        f"blue {blue[0]:.2f} {blue[1]:.2f}  "
        f"avoid L:{avoid[0]:.3f} R:{avoid[1]:.3f}  "
        f"mbon L:{mbon_left[0]:.2f},{mbon_left[1]:.2f},{mbon_left[2]:.2f} "
        f"R:{mbon_right[0]:.2f},{mbon_right[1]:.2f},{mbon_right[2]:.2f}  "
        f"S {short_term:.3f}  ARM {arm:.3f}  LTM {ltm:.3f}  phi {phi:.2f}  "
        f"shock {shocks}  punish {flag}  "
        f"wheel R:{right_v:.3f} L:{left_v:.3f}  "
        f"pulse R:{pulse_r} L:{pulse_l}  {cycle} {mode}  drive {drive}"
    )


def trace_mark(
    avoid: tuple[float, float],
    pulses: tuple[int, int],
    punished: bool,
    cycle: str,
    mode: str,
    arm: float,
    ltm: float,
) -> tuple[object, ...]:
    """Identity of a line. A new mark is worth printing before the next period."""
    return (
        round(avoid[0], 2),
        round(avoid[1], 2),
        pulses,
        bool(punished),
        cycle,
        mode,
        round(arm, 3),
        round(ltm, 3),
    )
