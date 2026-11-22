"""Green and yellow in the two overlapping eyes, then the shared PN code.

The eye split is fly-car's: the left eye is the left 65% of the frame, the
right eye is the right 65%, so the middle is in both. Hue is degrees, not
OpenCV's half-degree units. OpenCV is used for the camera when it is
installed; the masks themselves are numpy so the tests do not need it.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from brain.coding import pn_code
from brain.constants import CS_MINUS_HUE, CS_PLUS_HUE

LEFT_HI = 0.65
RIGHT_LO = 0.35
_THRESHOLDS = json.loads(Path(__file__).with_name("color_thresholds.json").read_text(encoding="utf-8"))


def bgr_to_hsv(frame: np.ndarray):
    """Hue in degrees, saturation and value in 0..255, from a uint8 BGR image."""
    image = np.asarray(frame)
    if image.ndim != 3 or image.shape[2] != 3:
        raise ValueError("frame must be BGR")
    b = image[..., 0].astype(np.float32)
    g = image[..., 1].astype(np.float32)
    r = image[..., 2].astype(np.float32)
    maximum = np.maximum(np.maximum(r, g), b)
    minimum = np.minimum(np.minimum(r, g), b)
    span = maximum - minimum
    hue = np.zeros_like(maximum)
    red = (maximum == r) & (span > 0)
    green = (maximum == g) & (span > 0)
    blue = (maximum == b) & (span > 0) & ~red & ~green
    hue[red] = ((g[red] - b[red]) / span[red]) % 6.0
    hue[green] = (b[green] - r[green]) / span[green] + 2.0
    hue[blue] = (r[blue] - g[blue]) / span[blue] + 4.0
    hue = hue * 60.0
    saturation = np.where(maximum > 0, span / maximum * 255.0, 0.0)
    return hue, saturation, maximum


def _mask(hue, saturation, value, name: str) -> np.ndarray:
    gate = _THRESHOLDS[name]
    return (
        (hue >= gate["hue_low"])
        & (hue <= gate["hue_high"])
        & (saturation >= gate["saturation"])
        & (value >= gate["value"])
    )


def _eye_mean(mask: np.ndarray, columns: np.ndarray) -> float:
    part = mask[:, columns]
    if part.size == 0:
        return 0.0
    return float(np.count_nonzero(part)) / float(part.size)


def eye_fractions(frame: np.ndarray, mirror: bool = False) -> dict[str, float]:
    image = np.asarray(frame)
    if mirror:
        image = image[:, ::-1, :]
    hue, saturation, value = bgr_to_hsv(image)
    width = int(image.shape[1])
    position = (np.arange(width) + 0.5) / float(width)
    left = position <= LEFT_HI
    right = position >= RIGHT_LO
    green = _mask(hue, saturation, value, "green")
    yellow = _mask(hue, saturation, value, "yellow")
    return {
        "green_l": _eye_mean(green, left),
        "green_r": _eye_mean(green, right),
        "yellow_l": _eye_mean(yellow, left),
        "yellow_r": _eye_mean(yellow, right),
    }


def pn_from_fractions(fractions: dict[str, float], gain: float = 1.0):
    scale = float(gain)
    left = pn_code(
        [scale * fractions["green_l"], scale * fractions["yellow_l"]],
        [CS_PLUS_HUE, CS_MINUS_HUE],
    )
    right = pn_code(
        [scale * fractions["green_r"], scale * fractions["yellow_r"]],
        [CS_PLUS_HUE, CS_MINUS_HUE],
    )
    return left, right


def pn_from_frame(frame: np.ndarray, mirror: bool = False, gain: float = 1.0):
    fractions = eye_fractions(frame, mirror=mirror)
    left, right = pn_from_fractions(fractions, gain=gain)
    return left, right, fractions


class Eyes:
    """Latest frame in, projection neurons out. A missing camera is darkness."""

    def __init__(self, mirror: bool = False, gain: float = 1.0):
        self.mirror = mirror
        self.gain = gain
        self.frame = None
        self.fractions = {"green_l": 0.0, "green_r": 0.0, "yellow_l": 0.0, "yellow_r": 0.0}
        self._capture = None
        self._camera_note = None

    def read(self):
        frame = self.frame if self.frame is not None else self._camera()
        if frame is None:
            dark = np.zeros(10, np.float32)
            return dark, dark, self.fractions
        left, right, self.fractions = pn_from_frame(frame, mirror=self.mirror, gain=self.gain)
        return left, right, self.fractions

    def close(self):
        if self._capture is not None:
            self._capture.release()
            self._capture = None

    def _camera(self):
        if self._camera_note == "off":
            return None
        if self._capture is None:
            try:
                import cv2
            except ImportError:
                self._camera_note = "off"
                print("camera: OpenCV が無いので、画面は暗いままです")
                return None
            self._capture = cv2.VideoCapture(0)
            if not self._capture.isOpened():
                self._camera_note = "off"
                print("camera: 開けなかったので、画面は暗いままです")
                self._capture.release()
                self._capture = None
                return None
            print("camera: /dev/video0")
        ok, frame = self._capture.read()
        if not ok:
            return None
        return frame
