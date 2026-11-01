"""A small JSON API plus the dashboard page, using only the standard library.

The browser drives the clock: while the user has the simulation running, the page
calls POST /api/tick every few hundred milliseconds and the server advances the
simulation by that much simulated time. There are no background threads.
"""
import json
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from .config import LIVE_PARAMS, SCENARIOS, STEPS, scenario_config
from .simulation import Simulation, compare

PAGE = Path(__file__).with_name("web") / "index.html"
MAX_TICK = 10.0          # simulated seconds per request


class App:
    def __init__(self, scenario="normal"):
        self.reset(scenario)

    def reset(self, scenario):
        sim = Simulation(scenario_config(scenario, duration=0))   # raises on bad input
        self.scenario, self.sim = scenario, sim

    def set_params(self, values):
        # check every value first so that a bad request changes nothing
        for name, value in values.items():
            if name not in LIVE_PARAMS:
                raise KeyError(f"{name!r} cannot be changed while running")
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ValueError(f"{name} must be a number")
        return {k: self.sim.set_param(k, v) for k, v in values.items()}

    def state(self, since=0):
        return {"scenario": self.scenario, **self.sim.state(since)}


def meta():
    return {
        "scenarios": {k: {"name": n, "text": d} for k, (n, d, _) in SCENARIOS.items()},
        "params": {k: {"min": lo, "max": hi, "int": kind is int} for k, (kind, lo, hi) in LIVE_PARAMS.items()},
        "steps": {k: v[0] for k, v in STEPS.items()},
    }


def make_handler(app):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):        # keep the console quiet
            pass

        def send(self, body, status=200, kind="application/json"):
            if kind == "application/json":
                body = json.dumps(body)
            data = body.encode() if isinstance(body, str) else body
            self.send_response(status)
            self.send_header("Content-Type", kind + "; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            url = urlparse(self.path)
            q = parse_qs(url.query)
            try:
                if url.path in ("/", "/index.html"):
                    self.send(PAGE.read_bytes(), kind="text/html")
                elif url.path == "/api/state":
                    self.send(app.state(int(q.get("since", ["0"])[0])))
                elif url.path == "/api/meta":
                    self.send(meta())
                elif url.path == "/api/compare":
                    keys = q.get("scenarios", [""])[0]
                    keys = [k for k in keys.split(",") if k] or None
                    for k in keys or []:
                        if k not in SCENARIOS:
                            raise KeyError(f"unknown scenario {k!r}")
                    self.send(compare(keys))
                else:
                    self.send({"error": "not found"}, 404)
            except (KeyError, ValueError) as e:
                self.send({"error": str(e)}, 400)

        def do_POST(self):
            try:
                length = int(self.headers.get("Content-Length") or 0)
                body = json.loads(self.rfile.read(length) or b"{}")
                if not isinstance(body, dict):
                    raise ValueError("body must be a JSON object")
                if self.path == "/api/tick":
                    seconds = float(body.get("seconds", 1))
                    if not 0 <= seconds <= MAX_TICK:
                        raise ValueError(f"seconds must be between 0 and {MAX_TICK:g}")
                    app.sim.advance(seconds)
                    self.send(app.state(int(body.get("since", 0))))
                elif self.path == "/api/reset":
                    app.reset(body.get("scenario", app.scenario))
                    self.send(app.state())
                elif self.path == "/api/params":
                    self.send(app.set_params(body))
                else:
                    self.send({"error": "not found"}, 404)
            except (KeyError, ValueError, TypeError) as e:
                self.send({"error": str(e).strip("'\"")}, 400)

    return Handler


def serve(host="127.0.0.1", port=8770, scenario="normal", open_browser=True):
    app = App(scenario)
    httpd = HTTPServer((host, port), make_handler(app))
    url = f"http://{host}:{port}/"
    print(f"Dashboard running at {url}  (Ctrl+C to stop)")
    if open_browser:
        webbrowser.open(url)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        httpd.server_close()
