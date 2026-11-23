"""Save and load of the learned brain, including the phone page."""

import json
import urllib.error
import urllib.parse
import urllib.request

import numpy as np
import pytest

from brain.brain import make_brain
from brain.coding import pn_code
from brain.constants import CS_PLUS_HUE
from brain.snapshot import SnapshotError
from memory_store import import_memory, load_memory, save_memory
from train_ui import TrainUI


def _red():
    return pn_code([0.5], [CS_PLUS_HUE])


def _learn(brain):
    red = _red()
    brain.begin_cycle()
    for i in range(60):
        if i == 30:
            brain.request_shock()
        brain.step(red, red, 0.02, in_train=True)
    brain.end_cycle()
    brain.t = brain.t  # clock already moved
    return red


def test_restore_then_matches_the_brain_that_kept_running():
    brain = make_brain(2, compression=5.0)
    red = _learn(brain)
    payload = json.loads(json.dumps(brain.snapshot()))
    other = make_brain(0, compression=1.0)
    other.restore(payload)
    assert np.array_equal(brain.mb.idx, other.mb.idx)
    assert np.array_equal(brain.mb.S, other.mb.S)
    assert np.array_equal(brain.dan.D, other.dan.D)
    assert other.compression == 5.0
    dark = np.zeros(10, np.float32)
    for i in range(80):
        view = red if i % 2 == 0 else dark
        if i % 19 == 0:
            brain.request_shock()
            other.request_shock()
        if i == 10:
            brain.begin_cycle()
            other.begin_cycle()
        if i == 50:
            brain.end_cycle()
            other.end_cycle()
        brain.step(view, view, 0.02, in_train=brain.in_cycle)
        other.step(view, view, 0.02, in_train=other.in_cycle)
    assert np.array_equal(brain.mb.S, other.mb.S)
    assert np.array_equal(brain.mb.A, other.mb.A)
    assert np.array_equal(brain.mb.L, other.mb.L)
    assert np.array_equal(brain.mb.eligibility, other.mb.eligibility)
    assert np.array_equal(brain.dan.D, other.dan.D)
    assert np.array_equal(brain.dan.a, other.dan.a)
    assert brain.n_shocks == other.n_shocks
    assert brain.t == pytest.approx(other.t)
    assert brain.in_cycle == other.in_cycle
    assert brain.mb.cycle_ends == pytest.approx(other.mb.cycle_ends)
    assert brain.mb.phi == pytest.approx(other.mb.phi)
    assert brain.avoid_spin == pytest.approx(other.avoid_spin)


def test_bad_version_or_shape_does_not_change_the_brain():
    brain = make_brain(1, compression=5.0)
    _learn(brain)
    before = brain.mb.S.copy()
    shocks = brain.n_shocks
    bad = brain.snapshot()
    bad["version"] = 9
    with pytest.raises(SnapshotError, match="版"):
        brain.restore(bad)
    bad = brain.snapshot()
    bad["S"] = [[0.0]]
    with pytest.raises(SnapshotError, match="形"):
        brain.restore(bad)
    bad = brain.snapshot()
    bad["app"] = "other"
    with pytest.raises(SnapshotError, match="fly-memento"):
        brain.restore(bad)
    assert np.array_equal(brain.mb.S, before)
    assert brain.n_shocks == shocks


def test_reset_returns_to_the_fly_from_boot():
    brain = make_brain(4, compression=5.0)
    birth = brain.mb.idx.copy()
    _learn(brain)
    loaded = make_brain(9, compression=1.0).snapshot()
    brain.restore(loaded)
    assert not np.array_equal(brain.mb.idx, birth)
    brain.reset_naive()
    assert np.array_equal(brain.mb.idx, birth)
    assert float(brain.mb.S.sum()) == 0.0
    assert float(brain.mb.L.sum()) == 0.0
    assert brain.n_shocks == 0
    assert brain.t == 0.0
    assert brain.in_cycle is False
    assert brain.compression == 5.0


def test_page_saves_loads_rejects_and_resets(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("FLY_MEMENTO_DATA", str(tmp_path))
    brain = make_brain(1, compression=5.0)
    red = _red()
    brain.mb.eligibility[:] = 1.0
    brain.request_shock()
    brain.step(red, red, 0.02, in_train=True)
    assert brain.n_shocks == 1
    learned = float(brain.mb.S.mean())
    page = TrainUI(brain, host="127.0.0.1", port=0).start()
    try:
        base = f"http://127.0.0.1:{page.port}"
        html = urllib.request.urlopen(base + "/", timeout=2).read().decode()
        assert "素朴に戻す" in html
        assert "自動で始める" in html
        assert "バツは周の外でも効く" in html
        saved = _post(base + "/memories", {"name": "朝のハエ"})
        assert saved["ok"] is True
        assert saved["name"] == "朝のハエ"
        again = _post(base + "/memories", {"name": "朝のハエ"})
        assert again["name"] == "朝のハエ-2"
        listing = json.loads(urllib.request.urlopen(base + "/memories", timeout=2).read())
        names = [row["name"] for row in listing["memories"]]
        assert "朝のハエ" in names
        brain.mb.S[:] = 0
        brain.n_shocks = 0
        loaded = _post(base + "/memories/" + urllib.parse.quote("朝のハエ") + "/load", {})
        assert loaded["ok"] is True
        assert brain.n_shocks == 1
        assert float(brain.mb.S.mean()) == pytest.approx(learned)
        blob = urllib.request.urlopen(
            base + "/memories/" + urllib.parse.quote("朝のハエ"), timeout=2
        ).read()
        bad = json.loads(blob)
        bad["version"] = 0
        with pytest.raises(urllib.error.HTTPError) as caught:
            _post(base + "/memories/upload", bad)
        error = json.loads(caught.value.read().decode())
        assert error["ok"] is False
        assert "版" in error["error"]
        assert brain.n_shocks == 1
        uploaded = _post_bytes(base + "/memories/upload", blob)
        assert uploaded["ok"] is True
        fresh = make_brain(3, compression=1.0)
        load_memory(fresh, "朝のハエ", directory=tmp_path / "memories")
        assert fresh.n_shocks == 1
        _delete(base + "/memories/" + urllib.parse.quote("朝のハエ"))
        listing = json.loads(urllib.request.urlopen(base + "/memories", timeout=2).read())
        assert "朝のハエ" not in [row["name"] for row in listing["memories"]]
        with pytest.raises(urllib.error.HTTPError) as missing:
            _post(base + "/memories/" + urllib.parse.quote("../secret") + "/load", {})
        assert json.loads(missing.value.read().decode())["ok"] is False
        brain.mb.S[:] = 1
        reset = _post(base + "/reset", {})
        assert reset["ok"] is True
        assert float(brain.mb.S.sum()) == 0.0
        assert brain.n_shocks == 0
    finally:
        page.close()
    text = capsys.readouterr().out
    assert "memory save" in text
    assert "memory load" in text
    assert "memory delete" in text
    assert "memory reset naive" in text
    # The directory the deploy script must leave alone.
    assert (tmp_path / "memories").is_dir()
    assert not (tmp_path / "ArduinoApps").exists()


def test_import_round_trip_file(tmp_path, monkeypatch):
    monkeypatch.setenv("FLY_MEMENTO_DATA", str(tmp_path))
    brain = make_brain(6, compression=5.0)
    _learn(brain)
    raw = json.dumps(brain.snapshot()).encode()
    other = make_brain(0, compression=1.0)
    info = import_memory(other, raw, name="持ち込み")
    assert info["name"] == "持ち込み"
    saved = json.loads((tmp_path / "memories" / "持ち込み.json").read_text(encoding="utf-8"))
    third = make_brain(1)
    third.restore(saved)
    assert np.allclose(other.mb.L, third.mb.L)
    assert other.n_shocks == brain.n_shocks


def _post(url, payload):
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode(),
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=2) as response:
        return json.loads(response.read().decode())


def _post_bytes(url, raw):
    request = urllib.request.Request(
        url,
        data=raw,
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=2) as response:
        return json.loads(response.read().decode())


def _delete(url):
    request = urllib.request.Request(url, method="DELETE")
    with urllib.request.urlopen(request, timeout=2) as response:
        return json.loads(response.read().decode())
