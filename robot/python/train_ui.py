"""Punish page for a phone on the same network.

The standard library serves it. The UNO Q web_ui brick would also work, but
that brick is a websocket dashboard and this page is the buttons in the same
process as the brain. Nothing else is required, so the app does not depend
on the brick.

GET  /                      the page
GET  /state                 JSON snapshot, including the auto-protocol
GET  /memories              saved brains
GET  /memories/<name>       download one file
POST /memories              save, optional {"name": "..."}
POST /memories/upload       JSON body of a memory file, then load it
POST /memories/<name>/load  load one saved brain
DELETE /memories/<name>     delete one saved brain
POST /reset                 back to the naive fly
POST /punish                one shock, applied on the next brain step
POST /cycle                 start a training cycle, or end it and rest
POST /flags                 {"eps": bool, "osc": bool}
POST /protocol/start        {"protocol": "spaced"|"massed"|"single", "rounds": 5, "cue": bool}
POST /protocol/abort
"""

from __future__ import annotations

import json
import threading
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from brain.snapshot import SnapshotError
from memory_store import StoreError, delete_memory, import_memory, list_memories, load_memory, read_memory, save_memory
from protocol import AutoProtocol, ProtocolError

_PAGE = Path(__file__).resolve().parents[1].joinpath("assets", "index.html").read_bytes()
_SEEING = {"red_l": 0.0, "red_r": 0.0, "blue_l": 0.0, "blue_r": 0.0}
_MAX_BODY = 2_000_000


class TrainUI:
    def __init__(self, brain, lock: threading.Lock | None = None, host="0.0.0.0", port=8000):
        self.brain = brain
        self.lock = lock if lock is not None else threading.Lock()
        self.seeing = dict(_SEEING)
        self.protocol = AutoProtocol(brain, save=self._autosave)
        handler = self._handler()
        self.httpd = ThreadingHTTPServer((host, port), handler)
        self.httpd.daemon_threads = True
        self._thread = threading.Thread(target=self.httpd.serve_forever, name="train-ui", daemon=True)

    @property
    def port(self) -> int:
        return int(self.httpd.server_address[1])

    def start(self) -> "TrainUI":
        self._thread.start()
        print(f"バツ画面  http://<この機械のアドレス>:{self.port}/", flush=True)
        return self

    def close(self):
        self.httpd.shutdown()
        self.httpd.server_close()

    def state(self) -> dict:
        with self.lock:
            snapshot = self.brain.status()
            snapshot["seeing"] = dict(self.seeing)
            snapshot["protocol"] = self.protocol.status()
        snapshot["avoid"] = [float(snapshot["avoid"][0]), float(snapshot["avoid"][1])]
        snapshot["wheels"] = [float(snapshot["wheels"][0]), float(snapshot["wheels"][1])]
        return snapshot

    def _autosave(self, brain, kind: str) -> str:
        stamp = time.strftime("%Y%m%d-%H%M%S")
        info = save_memory(brain, name=f"auto-{kind}-{stamp}")
        return info["name"]

    def _handler(self):
        ui = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, fmt, *args):
                return

            def _send(self, code, body, content_type, filename=None):
                data = body if isinstance(body, bytes) else body.encode("utf-8")
                self.send_response(code)
                self.send_header("Content-Type", content_type)
                self.send_header("Content-Length", str(len(data)))
                self.send_header("Cache-Control", "no-store")
                if filename:
                    # HTTP headers are latin-1. A Japanese name goes in filename*.
                    ascii_name = filename.encode("ascii", "ignore").decode() or "memory.json"
                    encoded = urllib.parse.quote(filename)
                    self.send_header(
                        "Content-Disposition",
                        f"attachment; filename=\"{ascii_name}\"; filename*=UTF-8''{encoded}",
                    )
                self.end_headers()
                self.wfile.write(data)

            def _json(self, code, payload):
                self._send(code, json.dumps(payload, ensure_ascii=False), "application/json")

            def _read_json(self):
                length = int(self.headers.get("Content-Length", "0") or 0)
                if length > _MAX_BODY:
                    raise StoreError("ファイルが大きすぎます。")
                raw = self.rfile.read(length) if length else b""
                if not raw:
                    return {}, raw
                try:
                    payload = json.loads(raw.decode("utf-8"))
                except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                    raise StoreError("JSON が読めません。") from exc
                if not isinstance(payload, dict):
                    raise StoreError("JSON がオブジェクトではありません。")
                return payload, raw

            def _fail(self, exc):
                self._json(400, {"ok": False, "error": str(exc)})

            def do_GET(self):
                kind, name = _split(self.path)
                try:
                    if kind == "page":
                        self._send(200, _PAGE, "text/html; charset=utf-8")
                        return
                    if kind == "state":
                        self._json(200, ui.state())
                        return
                    if kind == "memories":
                        self._json(200, {"memories": list_memories()})
                        return
                    if kind == "memory":
                        filename, data = read_memory(name)
                        self._send(200, data, "application/json", filename=filename)
                        return
                except (StoreError, SnapshotError) as exc:
                    self._fail(exc)
                    return
                self._send(404, "not found", "text/plain; charset=utf-8")

            def do_DELETE(self):
                kind, name = _split(self.path)
                if kind != "memory":
                    self._send(404, "not found", "text/plain; charset=utf-8")
                    return
                try:
                    self._json(200, {"ok": True, **delete_memory(name)})
                except (StoreError, SnapshotError) as exc:
                    self._fail(exc)

            def do_POST(self):
                kind, name = _split(self.path)
                try:
                    if kind == "punish":
                        with ui.lock:
                            ui.brain.request_shock()
                        self._json(200, {"ok": True})
                        return
                    if kind == "cycle":
                        with ui.lock:
                            phase = ui.brain.toggle_cycle()
                        self._json(200, {"cycle": phase})
                        return
                    if kind == "flags":
                        payload, _raw = self._read_json()
                        with ui.lock:
                            if "eps" in payload:
                                ui.brain.set_eps(bool(payload["eps"]))
                            if "osc" in payload:
                                ui.brain.set_oscillator(bool(payload["osc"]))
                        self._json(200, {"ok": True})
                        return
                    if kind == "memories":
                        payload, _raw = self._read_json()
                        chosen = payload.get("name")
                        with ui.lock:
                            info = save_memory(ui.brain, name=None if chosen is None else str(chosen))
                        self._json(200, {"ok": True, **info})
                        return
                    if kind == "upload":
                        length = int(self.headers.get("Content-Length", "0") or 0)
                        if length > _MAX_BODY:
                            raise StoreError("ファイルが大きすぎます。")
                        raw = self.rfile.read(length) if length else b""
                        with ui.lock:
                            info = import_memory(ui.brain, raw)
                            ui.protocol.halt()
                        self._json(200, {"ok": True, **info})
                        return
                    if kind == "load":
                        with ui.lock:
                            info = load_memory(ui.brain, name)
                            ui.protocol.halt()
                        self._json(200, {"ok": True, **info})
                        return
                    if kind == "reset":
                        with ui.lock:
                            ui.protocol.halt()
                            ui.brain.reset_naive()
                        print("memory reset naive", flush=True)
                        self._json(200, {"ok": True})
                        return
                    if kind == "start":
                        payload, _raw = self._read_json()
                        rounds = payload.get("rounds", 5)
                        if isinstance(rounds, bool) or not isinstance(rounds, int):
                            raise ProtocolError("周の数は 1 から 20 です。")
                        with ui.lock:
                            ui.protocol.start(
                                str(payload.get("protocol", "spaced")),
                                rounds=rounds,
                                cue=bool(payload.get("cue", False)),
                            )
                            status = ui.protocol.status()
                        self._json(200, {"ok": True, "protocol": status})
                        return
                    if kind == "abort":
                        with ui.lock:
                            ui.protocol.abort()
                            status = ui.protocol.status()
                        self._json(200, {"ok": True, "protocol": status})
                        return
                except (StoreError, SnapshotError, ProtocolError) as exc:
                    self._fail(exc)
                    return
                self._send(404, "not found", "text/plain; charset=utf-8")

        return Handler


def _split(url: str) -> tuple[str, str]:
    path = urllib.parse.unquote(url.split("?", 1)[0])
    if path in ("/", "/index.html"):
        return "page", ""
    if path == "/state":
        return "state", ""
    if path == "/punish":
        return "punish", ""
    if path == "/cycle":
        return "cycle", ""
    if path == "/flags":
        return "flags", ""
    if path == "/reset":
        return "reset", ""
    if path == "/protocol/start":
        return "start", ""
    if path == "/protocol/abort":
        return "abort", ""
    if path == "/memories":
        return "memories", ""
    if path == "/memories/upload":
        return "upload", ""
    if path.startswith("/memories/"):
        rest = path[len("/memories/") :]
        if rest.endswith("/load") and rest != "/load":
            return "load", rest[: -len("/load")]
        if rest and "/" not in rest:
            return "memory", rest
    return "", ""
