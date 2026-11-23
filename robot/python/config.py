"""Knobs for the UNO Q app. The brain's equations live in ``brain``."""

# Measured chassis. Rear track is 9.75 cm between the rear wheels, wheelbase
# is 8.0 cm from the rear axle to the front axle. The pulse map does not use
# them. The arena unicycle keeps brain.constants.TRACK (0.12 m).
from brain.constants import CHASSIS_REAR_TRACK_M as REAR_TRACK_M
from brain.constants import CHASSIS_WHEELBASE_M as WHEELBASE_M

# Biological minutes per robot-second. The single knob is
# brain.constants.DEFAULT_COMPRESSION; this name is what the robot reads.
# 5 → 24 h is 4.8 min, and the oscillator is scaled so the biological
# trajectory matches compression 1.
from brain.constants import DEFAULT_COMPRESSION as COMPRESSION
from pulse import CRUISE_MPS, CRUISE_PULSE, FORWARD_START

# Picture left is the robot's right when this is True.
MIRROR = False

# Brain step. Matches fly-car TICK_S.
TICK_S = 0.02

# Camera refresh. Slower than the brain, same idea as fly-car COUNT_S.
COUNT_S = 0.10

# Idle heartbeat. While colour, avoidance, or the wheels are active,
# main.py also prints every DETAIL_S and whenever the command changes.
LOG_S = 1.0
DETAIL_S = 0.10

# A stalled loop may catch up, but not by more than this.
MAX_CATCHUP_S = 0.70

# Phone page. App Lab must publish this port (see app.yaml).
PORT = 8000

# How strongly a filled eye drives the projection neurons.
# 1.0 means "this colour fills the eye" has intensity 1, which is brighter
# than a lamp at half a metre in the arena sim. Turn it down if the robot
# rushes every patch of colour. A fill under about 0.14 of one eye stays
# under the motor dead zone at this gain; raise it if a small real panel
# should crawl.
COLOR_GAIN = 1.0

# Dark cruise added to both wheels, in the same units as brain WHEEL_BIAS
# (dimensionless, then multiplied by VMAX). The arena keeps 0.35, which is
# 0.021 m/s and pulse 17, above the forward dead zone of 13, so the robot
# creeps with no target. fly-car has no baseline drive. Leave this at 0
# unless that wander is wanted; 0.35 turns the old creep back on.
EXPLORE_BIAS = 0.0

# Speeds quieter than this are sent as 0 m/s and pulse 0. The default is the
# forward dead zone: pulse 13 is 13 * 0.20/160 = 0.01625 m/s.
WHEEL_STOP_MPS = FORWARD_START * CRUISE_MPS / CRUISE_PULSE
