"""Knobs for the UNO Q app. The brain's equations live in ``brain``."""

# Picture left is the robot's right when this is True.
MIRROR = False

# Brain step. Matches fly-car TICK_S.
TICK_S = 0.02

# Camera refresh. Slower than the brain, same idea as fly-car COUNT_S.
COUNT_S = 0.10

# A stalled loop may catch up, but not by more than this.
MAX_CATCHUP_S = 0.70

# Phone page. App Lab must publish this port (see app.yaml).
PORT = 8000

# Biological minutes per robot-second. 1 → 24 h is 24 min. 5 → 24 h is 4.8 min.
COMPRESSION = 1.0

# How strongly a filled eye drives the projection neurons.
# 1.0 means "this colour fills the eye" has intensity 1, which is brighter
# than a lamp at half a metre in the arena sim. Turn it down if the robot
# rushes every patch of colour.
COLOR_GAIN = 1.0
