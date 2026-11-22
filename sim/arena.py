"""2D arena, two lamps, and a robot that carries a ``brain.Brain``.

The geometry is the research prototype: a 1 m square, lamps 10 cm wide, the
start at the bottom, and a bar 3 cm behind the CS+ lamp that counts as a
shock. Wheel noise is an Ornstein–Uhlenbeck pair. The brain itself lives in
``brain`` and is not duplicated here.
"""

from __future__ import annotations

import numpy as np

from brain.brain import Brain
from brain.coding import pn_code
from brain.constants import TRACK, VMAX

LX, LY = 0.25, 0.35
START = (0.0, -0.3)


class World:
    def __init__(self, lights, bar=None, size=(1.0, 1.0)):
        self.lights = lights  # (x, y, hue)
        self.bar = bar  # (x, y) of the shock bar, or None
        self.size = size


def eye_intensity(pos, heading, lights, rng):
    """Projection-neuron code for the left eye and the right eye."""
    out = []
    for lo, hi in ((-12.0, 40.0), (-40.0, 12.0)):
        weights = []
        hues = []
        for x, y, hue in lights:
            dx, dy = x - pos[0], y - pos[1]
            distance = float(np.hypot(dx, dy))
            angle = np.degrees(np.arctan2(dy, dx) - heading)
            angle = (angle + 180.0) % 360.0 - 180.0
            half_width = np.degrees(np.arctan2(0.05, max(distance, 1e-6)))
            gate = 1.0 / (1.0 + np.exp(-(angle - lo + half_width) / 3.0))
            gate /= 1.0 + np.exp((angle - hi - half_width) / 3.0)
            weights.append(gate / (1.0 + (distance / 0.3) ** 2) * (1.0 + 0.05 * rng.standard_normal()))
            hues.append(hue)
        if lights:
            out.append(pn_code(np.maximum(weights, 0.0), hues))
        else:
            out.append(np.zeros(10, np.float32))
    return out


class Agent:
    def __init__(self, brain: Brain):
        self.brain = brain
        self.rng = np.random.default_rng(int(brain.rng.integers(1 << 30)))
        self.pos = np.zeros(2)
        self.heading = np.pi / 2
        self.noise = np.zeros(2)

    def reset_pose(self):
        self.pos = np.array(START, dtype=float)
        self.heading = np.pi / 2
        self.noise[:] = 0.0

    def drive(self, world, seconds, dt=0.02, in_train=False, record=False, stop_r=0.12, stop_on_choice=False):
        trace = []
        bumps = 0
        last_bump = -9.0
        choice = None
        steps = int(round(seconds / dt))
        for i in range(steps):
            pn_left, pn_right = eye_intensity(self.pos, self.heading, world.lights, self.rng)
            _al, _ar, wheel_left, wheel_right = self.brain.sense(pn_left, pn_right)
            self.noise += dt / 0.5 * (-self.noise) + 0.25 * VMAX * np.sqrt(2 * dt / 0.5) * self.rng.standard_normal(2)
            wheel_left += self.noise[0]
            wheel_right += self.noise[1]
            speed = (wheel_left + wheel_right) / 2.0
            omega = (wheel_right - wheel_left) / TRACK
            new = self.pos + dt * speed * np.array([np.cos(self.heading), np.sin(self.heading)])
            self.heading += dt * omega
            hit = False
            if world.bar is not None and new[1] > world.bar[1] and abs(new[0] - world.bar[0]) < 0.15:
                new[1] = world.bar[1]
                hit = True
            width, height = world.size
            new = np.clip(new, [-width / 2, -height / 2], [width / 2, height / 2])
            self.pos = new
            if hit and self.brain.t - last_bump >= 1.0:
                self.brain.request_shock()
                bumps += 1
                last_bump = self.brain.t
            step = self.brain.integrate(dt, in_train=in_train)
            if record and i % 5 == 0:
                trace.append((self.brain.t, self.pos[0], self.pos[1], self.heading, step.avoid_left, step.avoid_right, float(hit)))
            if choice is None and world.bar is None:
                for index, (x, y, _hue) in enumerate(world.lights):
                    if np.hypot(x - self.pos[0], y - self.pos[1]) < stop_r:
                        choice = index
                if choice is not None and not record and stop_on_choice:
                    break
        return {"bumps": bumps, "choice": choice, "traj": np.array(trace) if trace else np.zeros((0, 7))}
