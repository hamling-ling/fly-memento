"""Versioned JSON for the learned brain.

The file has to be enough to resume behaviour: Kenyon wiring, the S / ARM /
LTM weights, eligibility, the oscillator, the round clock, fatigue, the
biological time, the shock count, and compression. ``parse`` checks the
shape before ``apply`` touches the live brain.
"""

from __future__ import annotations

import numpy as np

from brain.constants import N_COMPARTMENTS, N_PN

MEMORY_VERSION = 1
APP_NAME = "fly-memento"


class SnapshotError(ValueError):
    """The file is the wrong version or the wrong shape."""


def dump(brain) -> dict:
    mb = brain.mb
    dan = brain.dan
    payload = {
        "app": APP_NAME,
        "version": MEMORY_VERSION,
        "seed": int(brain.seed),
        "compression": float(brain.compression),
        "t": float(brain.t),
        "bio_min": float(brain.bio_min),
        "us_ext": float(brain.us_ext),
        "shock_pending": bool(brain.shock_pending),
        "last_shock": float(brain.last_shock),
        "n_shocks": int(brain.n_shocks),
        "shock_elig": float(brain.shock_elig),
        "in_cycle": bool(brain.in_cycle),
        "cycle_start": float(brain.cycle_start),
        "eps_on": bool(brain.eps_on),
        "eps_value": float(brain._eps_value),
        "avoid_spin": float(brain.avoid_spin),
        "variant": str(mb.variant),
        "learn": bool(mb.learn),
        "k": int(mb.k),
        "gains": _floats(mb.gains),
        "norm": {key: float(value) for key, value in dict(mb.norm).items()},
        "idx": mb.idx.astype(int).tolist(),
        "jitter": _floats(mb.jitter),
        "S": _floats(mb.S),
        "A": _floats(mb.A),
        "L": _floats(mb.L),
        "eligibility": _floats(mb.eligibility),
        "z_slow": float(mb.z_slow),
        "phi": float(mb.phi),
        "win_until": float(mb.win_until),
        "erase_until": float(mb.erase_until),
        "cycle_ends": [float(value) for value in mb.cycle_ends],
        "D": _floats(dan.D),
        "a": _floats(dan.a),
        "off": float(dan.off),
        "gs": _floats(dan.gs),
        "ga": _floats(dan.ga),
        "tau_a": _floats(dan.tau_a),
        "tau": float(dan.tau),
        "dmax": float(dan.dmax),
        "eps": float(dan.eps),
        "osc": bool(dan.osc),
    }
    parse(payload, brain)
    return payload


def load(brain, payload: dict) -> None:
    apply(brain, parse(payload, brain))


def parse(payload, brain) -> dict:
    if not isinstance(payload, dict):
        raise SnapshotError("記憶ファイルがオブジェクトではありません。")
    if payload.get("app") != APP_NAME:
        raise SnapshotError("このファイルは fly-memento の記憶ではありません。")
    version = payload.get("version")
    if version != MEMORY_VERSION:
        raise SnapshotError(
            f"記憶ファイルの版が違います（ファイルは {version}、このアプリは {MEMORY_VERSION}）。"
        )
    n_kc = int(brain.mb.n_kc)
    claws = int(brain.mb.idx.shape[1])
    n_comp = N_COMPARTMENTS
    compression = _finite(payload, "compression")
    if not 0.0 < compression <= 20.0:
        raise SnapshotError("圧縮の値が不正です。")
    t = _finite(payload, "t")
    if t < 0.0:
        raise SnapshotError("時刻が不正です。")
    if "bio_min" in payload:
        bio = _finite(payload, "bio_min")
        if abs(bio - t * compression) > 1e-2 * max(1.0, abs(bio)):
            raise SnapshotError("生物時刻が圧縮とロボット時刻に合いません。")
    variant = payload.get("variant")
    if variant not in {"COI", "ADD"}:
        raise SnapshotError("記憶の variant が違います。")
    k = payload.get("k")
    if not isinstance(k, int) or isinstance(k, bool) or not 1 <= k <= n_kc:
        raise SnapshotError("記憶の k が違います。")
    n_shocks = payload.get("n_shocks")
    if not isinstance(n_shocks, int) or isinstance(n_shocks, bool) or n_shocks < 0:
        raise SnapshotError("罰の回数が不正です。")
    norm = payload.get("norm")
    if not isinstance(norm, dict) or set(norm) != {"A101", "A103", "ADD", "COI"}:
        raise SnapshotError("記憶の正規化定数が違います。")
    parsed_norm = {}
    for key, value in norm.items():
        try:
            number = float(value)
        except (TypeError, ValueError) as exc:
            raise SnapshotError("記憶の正規化定数が読めません。") from exc
        if not np.isfinite(number) or number <= 0.0:
            raise SnapshotError("記憶の正規化定数が不正です。")
        parsed_norm[key] = number
    idx = _array(payload, "idx", (n_kc, claws), int)
    if np.any(idx < 0) or np.any(idx >= N_PN):
        raise SnapshotError("ケニヨン細胞の配線が範囲外です。")
    cycle_ends = payload.get("cycle_ends")
    if not isinstance(cycle_ends, list):
        raise SnapshotError("周の記録がありません。")
    ends = []
    for value in cycle_ends:
        try:
            number = float(value)
        except (TypeError, ValueError) as exc:
            raise SnapshotError("周の記録が読めません。") from exc
        if not np.isfinite(number):
            raise SnapshotError("周の記録に不正な数があります。")
        ends.append(number)
    return {
        "seed": int(payload.get("seed", brain.seed)),
        "compression": compression,
        "t": t,
        "us_ext": _finite(payload, "us_ext"),
        "shock_pending": bool(payload.get("shock_pending", False)),
        "last_shock": _finite(payload, "last_shock"),
        "n_shocks": int(n_shocks),
        "shock_elig": _finite(payload, "shock_elig"),
        "in_cycle": bool(payload.get("in_cycle", False)),
        "cycle_start": _finite(payload, "cycle_start"),
        "eps_on": bool(payload.get("eps_on", True)),
        "eps_value": _positive(payload, "eps_value"),
        "avoid_spin": _finite(payload, "avoid_spin"),
        "variant": variant,
        "learn": bool(payload.get("learn", True)),
        "k": int(k),
        "gains": _array(payload, "gains", (n_comp,), np.float32),
        "norm": parsed_norm,
        "idx": idx.astype(np.uint8),
        "jitter": _array(payload, "jitter", (n_kc,), np.float32),
        "S": _array(payload, "S", (n_comp, n_kc), np.float32),
        "A": _array(payload, "A", (n_comp, n_kc), np.float32),
        "L": _array(payload, "L", (n_comp, n_kc), np.float32),
        "eligibility": _array(payload, "eligibility", (n_kc,), np.float32),
        "z_slow": _finite(payload, "z_slow"),
        "phi": _finite(payload, "phi"),
        "win_until": _finite(payload, "win_until"),
        "erase_until": _finite(payload, "erase_until"),
        "cycle_ends": ends,
        "D": _array(payload, "D", (2,), np.float32),
        "a": _array(payload, "a", (2,), np.float32),
        "off": _finite(payload, "off"),
        "gs": _array(payload, "gs", (2,), np.float32),
        "ga": _array(payload, "ga", (2,), np.float32),
        "tau_a": _array(payload, "tau_a", (2,), np.float32),
        "tau": _positive(payload, "tau"),
        "dmax": _positive(payload, "dmax"),
        "eps": _finite(payload, "eps"),
        "osc": bool(payload.get("osc", True)),
    }


def apply(brain, parsed: dict) -> None:
    mb = brain.mb
    dan = brain.dan
    brain.seed = int(parsed["seed"])
    brain.compression = float(parsed["compression"])
    brain.t = float(parsed["t"])
    brain.us_ext = float(parsed["us_ext"])
    brain.shock_pending = bool(parsed["shock_pending"])
    brain.last_shock = float(parsed["last_shock"])
    brain.n_shocks = int(parsed["n_shocks"])
    brain.shock_elig = float(parsed["shock_elig"])
    brain.in_cycle = bool(parsed["in_cycle"])
    brain.cycle_start = float(parsed["cycle_start"])
    brain.eps_on = bool(parsed["eps_on"])
    brain._eps_value = float(parsed["eps_value"])
    brain.avoid_spin = float(parsed["avoid_spin"])
    mb.variant = parsed["variant"]
    mb.learn = bool(parsed["learn"])
    mb.k = int(parsed["k"])
    mb.gains = np.array(parsed["gains"], np.float32, copy=True)
    mb.norm = dict(parsed["norm"])
    mb.idx = np.array(parsed["idx"], np.uint8, copy=True)
    mb.jitter = np.array(parsed["jitter"], np.float32, copy=True)
    mb.S = np.array(parsed["S"], np.float32, copy=True)
    mb.A = np.array(parsed["A"], np.float32, copy=True)
    mb.L = np.array(parsed["L"], np.float32, copy=True)
    mb.eligibility = np.array(parsed["eligibility"], np.float32, copy=True)
    mb.z_slow = float(parsed["z_slow"])
    mb.phi = float(parsed["phi"])
    mb.win_until = float(parsed["win_until"])
    mb.erase_until = float(parsed["erase_until"])
    mb.cycle_ends = [float(value) for value in parsed["cycle_ends"]]
    dan.D = np.array(parsed["D"], np.float32, copy=True)
    dan.a = np.array(parsed["a"], np.float32, copy=True)
    dan.off = float(parsed["off"])
    dan.gs = np.array(parsed["gs"], np.float32, copy=True)
    dan.ga = np.array(parsed["ga"], np.float32, copy=True)
    dan.tau_a = np.array(parsed["tau_a"], np.float32, copy=True)
    dan.tau = float(parsed["tau"])
    dan.dmax = float(parsed["dmax"])
    dan.eps = float(parsed["eps"])
    dan.osc = bool(parsed["osc"])
    brain.last = None
    brain._seen = None


def _floats(array) -> list:
    return np.asarray(array, dtype=np.float64).tolist()


def _finite(payload, key) -> float:
    if key not in payload:
        raise SnapshotError(f"記憶に {key} がありません。")
    try:
        number = float(payload[key])
    except (TypeError, ValueError) as exc:
        raise SnapshotError(f"{key} の数値が読めません。") from exc
    if not np.isfinite(number):
        raise SnapshotError(f"{key} に不正な数があります。")
    return number


def _positive(payload, key) -> float:
    number = _finite(payload, key)
    if number <= 0.0:
        raise SnapshotError(f"{key} の値が不正です。")
    return number


def _array(payload, key, shape, dtype):
    if key not in payload:
        raise SnapshotError(f"記憶に {key} がありません。")
    try:
        if dtype is int:
            value = np.asarray(payload[key], dtype=np.int64)
        else:
            value = np.asarray(payload[key], dtype=dtype)
    except (TypeError, ValueError) as exc:
        raise SnapshotError(f"{key} の数値が読めません。") from exc
    if value.shape != shape:
        raise SnapshotError(f"{key} の形が違います（{list(value.shape)}、必要なのは {list(shape)}）。")
    if dtype is not int and not np.isfinite(value).all():
        raise SnapshotError(f"{key} に不正な数があります。")
    return value
