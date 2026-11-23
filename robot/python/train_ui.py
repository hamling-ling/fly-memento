"""Punish page for a phone on the same network.

The standard library serves it. The UNO Q web_ui brick would also work, but
that brick is a websocket dashboard and this page is one button plus two
switches in the same process as the brain. Nothing else is required, so the
app does not depend on the brick.

GET /           the page
GET /state      JSON snapshot
POST /punish    one shock, applied on the next brain step
POST /cycle     start a training cycle, or end it and rest
POST /flags     {"eps": bool, "osc": bool}
"""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

_PAGE = Path(__file__).resolve().parents[1].joinpath("assets", "index.html").read_bytes()
_SEEING = {"red_l": 0.0, "red_r": 0.0, "blue_l": 0.0, "blue_r": 0.0}


class TrainUI:
    def __init__(self, brain, lock: threading.Lock | None = None, host="0.0.0.0", port=8000):
        self.brain = brain
        self.lock = lock if lock is not None else threading.Lock()
        self.seeing = dict(_SEEING)
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
        snapshot["avoid"] = [float(snapshot["avoid"][0]), float(snapshot["avoid"][1])]
        snapshot["wheels"] = [float(snapshot["wheels"][0]), float(snapshot["wheels"][1])]
        return snapshot

    def _handler(self):
        ui = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, fmt, *args):
                return

            def _send(self, code, body, content_type):
                data = body if isinstance(body, bytes) else body.encode("utf-8")
                self.send_response(code)
                self.send_header("Content-Type", content_type)
                self.send_header("Content-Length", str(len(data)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(data)

            def do_GET(self):
                path = self.path.split("?", 1)[0]
                if path in ("/", "/index.html"):
                    self._send(200, _PAGE, "text/html; charset=utf-8")
                    return
                if path == "/state":
                    self._send(200, json.dumps(ui.state()), "application/json")
                    return
                self._send(404, "not found", "text/plain; charset=utf-8")

            def do_POST(self):
                path = self.path.split("?", 1)[0]
                length = int(self.headers.get("Content-Length", "0") or 0)
                raw = self.rfile.read(length) if length else b""
                if path == "/punish":
                    with ui.lock:
                        ui.brain.request_shock()
                    self._send(200, json.dumps({"ok": True}), "application/json")
                    return
                if path == "/cycle":
                    with ui.lock:
                        phase = ui.brain.toggle_cycle()
                    self._send(200, json.dumps({"cycle": phase}), "application/json")
                    return
                if path == "/flags":
                    try:
                        payload = json.loads(raw.decode("utf-8") or "{}")
                    except json.JSONDecodeError:
                        self._send(400, json.dumps({"ok": False}), "application/json")
                        return
                    with ui.lock:
                        if "eps" in payload:
                            ui.brain.set_eps(bool(payload["eps"]))
                        if "osc" in payload:
                            ui.brain.set_oscillator(bool(payload["osc"]))
                    self._send(200, json.dumps({"ok": True}), "application/json")
                    return
                self._send(404, "not found", "text/plain; charset=utf-8")

        return Handler
