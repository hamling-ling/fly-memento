"""Reduced mushroom-body brain shared by the arena sim and the UNO Q app.

Time compression is ``bio_min_per_robot_s``: how many biological minutes pass
during one second of robot (or simulator) time. The research runs used 1
(one robot-second stands for one biological minute, so 24 h is 24 min).
The default is 5, so the same day passes in 4.8 min. The oscillator,
eligibility and shock pulse scale with it, and a 50 Hz tick is subdivided
so each Euler piece stays the compression-1 step.
"""

from brain.brain import Brain, make_brain
from brain.budget import flop_budget, mcu_state_bytes
from brain.coding import pn_code
from brain.wheels import wheel_speeds

__all__ = [
    "Brain",
    "flop_budget",
    "make_brain",
    "mcu_state_bytes",
    "pn_code",
    "wheel_speeds",
]
