"""Red and blue fill of a camera frame, then the shared PN code.

The count follows fly-car's ``occupancy.py``. OpenCV converts BGR to HSV and
the hue byte is doubled back to degrees. Gates come from
``color_thresholds.json``: red is a wrap, ``hue <= hue_low`` or
``hue >= hue_wrap``, and blue is one closed interval. A connected region
smaller than ``REGION_MIN_FRACTION`` of the frame is dropped. Frames wider
than ``COUNT_W`` are shrunk before the count. The left eye is columns whose
centre ``p <= 0.65``, the right eye is ``p >= 0.35``, and the middle is in
both. This app does not read loom or a red centroid.

A counted red pixel is coded as ``CS_PLUS_HUE`` (0°) and a counted blue
pixel as ``CS_MINUS_HUE`` (240°). The measured hue is not passed to the
brain. An eye fill below ``fraction_floor`` is left in the log and is not
given to the projection neurons.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from brain.coding import pn_code
from brain.constants import CS_MINUS_HUE, CS_PLUS_HUE

try:
    import cv2
except ImportError:  # the punish page still runs; the eyes stay dark
    cv2 = None

LEFT_HI = 0.65
RIGHT_LO = 0.35
# fly-car loom.REGION_MIN_FRACTION. A speck smaller than this is not a panel.
REGION_MIN_FRACTION = 0.002
# fly-car occupancy.COUNT_W. Counting reads this width; the log frame is not saved here.
COUNT_W = 320
DEFAULT_FRACTION_FLOOR = 0.05
THRESHOLDS_PATH = Path(__file__).with_name("color_thresholds.json")
_KEYS = ("red_l", "red_r", "blue_l", "blue_r")


def _mapping(raw: object, label: str) -> dict:
    if not isinstance(raw, dict):
        raise ValueError(f"{label} is not an object")
    return raw


def _integer(block: dict, key: str, low: int, high: int, label: str) -> int:
    if key not in block:
        raise ValueError(f"{label} is missing {key}")
    value = block[key]
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{label} {key} is not an integer")
    if value < low or value > high:
        raise ValueError(f"{label} {key} is out of range")
    return value


def load_cuts(path: Path) -> dict[str, float]:
    """Read fly-car's eight gates, plus this app's ``fraction_floor``."""
    if not path.is_file():
        raise FileNotFoundError(f"missing colour gates: {path}")
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"colour gates are not JSON: {path}") from exc
    document = _mapping(raw, path.name)
    red = _mapping(document.get("red"), "red")
    blue = _mapping(document.get("blue"), "blue")
    red_s = _integer(red, "saturation", 0, 255, "red")
    red_v = _integer(red, "value", 0, 255, "red")
    red_low = _integer(red, "hue_low", -1, 360, "red")
    red_wrap = _integer(red, "hue_wrap", 0, 360, "red")
    blue_s = _integer(blue, "saturation", 0, 255, "blue")
    blue_v = _integer(blue, "value", 0, 255, "blue")
    blue_low = _integer(blue, "hue_low", 0, 360, "blue")
    blue_high = _integer(blue, "hue_high", 0, 360, "blue")
    if blue_low > blue_high:
        raise ValueError("blue hue_low is above hue_high")
    floor = document.get("fraction_floor", DEFAULT_FRACTION_FLOOR)
    if isinstance(floor, bool) or not isinstance(floor, (int, float)):
        raise ValueError("fraction_floor is not a number")
    floor = float(floor)
    if not 0.0 <= floor <= 1.0:
        raise ValueError("fraction_floor is out of range")
    return {
        "RED_S": red_s,
        "RED_V": red_v,
        "RED_H_LOW": red_low,
        "RED_H_WRAP": red_wrap,
        "BLUE_S": blue_s,
        "BLUE_V": blue_v,
        "BLUE_H_LOW": blue_low,
        "BLUE_H_HIGH": blue_high,
        "FRACTION_FLOOR": floor,
    }


_CUTS = load_cuts(THRESHOLDS_PATH)
RED_S = int(_CUTS["RED_S"])
RED_V = int(_CUTS["RED_V"])
RED_H_LOW = int(_CUTS["RED_H_LOW"])
RED_H_WRAP = int(_CUTS["RED_H_WRAP"])
BLUE_S = int(_CUTS["BLUE_S"])
BLUE_V = int(_CUTS["BLUE_V"])
BLUE_H_LOW = int(_CUTS["BLUE_H_LOW"])
BLUE_H_HIGH = int(_CUTS["BLUE_H_HIGH"])
FRACTION_FLOOR = float(_CUTS["FRACTION_FLOOR"])


def _need_cv2():
    if cv2 is None:
        raise RuntimeError("OpenCV is not installed, so colours are not counted")


def color_masks(frame_bgr: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Boolean red and blue masks for a uint8 BGR frame."""
    _need_cv2()
    frame = np.asarray(frame_bgr)
    if frame.ndim != 3 or frame.shape[2] != 3:
        raise ValueError("frame must be a BGR image")
    if frame.dtype != np.uint8:
        raise ValueError("frame must be uint8")
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    hue = hsv[:, :, 0].astype(np.int16) * 2
    saturation = hsv[:, :, 1]
    value = hsv[:, :, 2]
    red = (saturation >= RED_S) & (value >= RED_V) & ((hue <= RED_H_LOW) | (hue >= RED_H_WRAP))
    blue = (hue >= BLUE_H_LOW) & (hue <= BLUE_H_HIGH) & (saturation >= BLUE_S) & (value >= BLUE_V)
    return _large_regions(red), _large_regions(blue)


def _large_regions(mask: np.ndarray) -> np.ndarray:
    """Drop connected regions smaller than ``REGION_MIN_FRACTION`` of the frame."""
    _need_cv2()
    image = np.ascontiguousarray(np.asarray(mask, dtype=bool))
    if image.size == 0 or not np.any(image):
        return image
    count, labels, stats, _centroids = cv2.connectedComponentsWithStats(
        image.astype(np.uint8), connectivity=8
    )
    if count <= 1:
        return image
    keep = stats[:, cv2.CC_STAT_AREA] >= REGION_MIN_FRACTION * image.size
    keep[0] = False
    return keep[labels]


def _count_frame(frame: np.ndarray) -> np.ndarray:
    image = np.asarray(frame)
    if image.ndim != 3 or int(image.shape[1]) <= COUNT_W:
        return image
    _need_cv2()
    height = max(1, int(round(image.shape[0] * COUNT_W / image.shape[1])))
    return cv2.resize(image, (COUNT_W, height), interpolation=cv2.INTER_AREA)


def range_means(mask: np.ndarray) -> tuple[float, float]:
    """Mean of ``mask`` on the left eye and the right eye."""
    image = np.asarray(mask)
    if image.ndim != 2:
        raise ValueError("mask must be a 2D image")
    width = int(image.shape[1])
    if width == 0 or image.size == 0:
        return 0.0, 0.0
    position = (np.arange(width) + 0.5) / float(width)
    left = image[:, position <= LEFT_HI]
    right = image[:, position >= RIGHT_LO]
    left_mean = float(np.count_nonzero(left)) / float(left.size) if left.size else 0.0
    right_mean = float(np.count_nonzero(right)) / float(right.size) if right.size else 0.0
    return left_mean, right_mean


def eye_fractions(frame: np.ndarray, mirror: bool = False) -> dict[str, float]:
    """Raw eye fills in 0..1. The fraction floor is not applied here."""
    red, blue = color_masks(_count_frame(frame))
    if mirror:
        red = np.ascontiguousarray(np.fliplr(red))
        blue = np.ascontiguousarray(np.fliplr(blue))
    red_l, red_r = range_means(red)
    blue_l, blue_r = range_means(blue)
    return {"red_l": red_l, "red_r": red_r, "blue_l": blue_l, "blue_r": blue_r}


def gate_fractions(fractions: dict[str, float], floor: float | None = None) -> dict[str, float]:
    """Zero an eye fill below ``floor``. The raw number stays in the log."""
    limit = FRACTION_FLOOR if floor is None else float(floor)
    gated: dict[str, float] = {}
    for key in _KEYS:
        value = float(fractions.get(key, 0.0))
        gated[key] = 0.0 if value < limit else value
    return gated


def pn_from_fractions(fractions: dict[str, float], gain: float = 1.0, floor: float | None = None):
    scale = float(gain)
    gated = gate_fractions(fractions, floor)
    left = pn_code(
        [scale * gated["red_l"], scale * gated["blue_l"]],
        [CS_PLUS_HUE, CS_MINUS_HUE],
    )
    right = pn_code(
        [scale * gated["red_r"], scale * gated["blue_r"]],
        [CS_PLUS_HUE, CS_MINUS_HUE],
    )
    return left, right


def pn_from_frame(frame: np.ndarray, mirror: bool = False, gain: float = 1.0, floor: float | None = None):
    fractions = eye_fractions(frame, mirror=mirror)
    left, right = pn_from_fractions(fractions, gain=gain, floor=floor)
    return left, right, fractions


class Eyes:
    """Latest frame in, projection neurons out. A missing camera is darkness."""

    def __init__(self, mirror: bool = False, gain: float = 1.0):
        self.mirror = mirror
        self.gain = gain
        self.frame = None
        self.fractions = {key: 0.0 for key in _KEYS}
        self._capture = None
        self._camera_note = None

    def read(self):
        frame = self.frame if self.frame is not None else self._camera()
        if frame is None:
            dark = np.zeros(10, np.float32)
            return dark, dark, self.fractions
        try:
            left, right, self.fractions = pn_from_frame(frame, mirror=self.mirror, gain=self.gain)
        except RuntimeError as exc:
            if self._camera_note != "opencv":
                print(f"camera: {exc}")
                self._camera_note = "opencv"
            dark = np.zeros(10, np.float32)
            self.fractions = {key: 0.0 for key in _KEYS}
            return dark, dark, self.fractions
        return left, right, self.fractions

    def close(self):
        if self._capture is not None:
            self._capture.release()
            self._capture = None

    def _camera(self):
        if self._camera_note == "off":
            return None
        if cv2 is None:
            self._camera_note = "off"
            print("camera: OpenCV が無いので、画面は暗いままです")
            return None
        if self._capture is None:
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
