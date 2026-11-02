import json
import threading
import unittest
import urllib.error
import urllib.request
from http.server import HTTPServer

from delivery import SCENARIOS, Config, Simulation, compare, scenario_config
from delivery.colleagues import Colleague
from delivery.mediator import Mediator
from delivery.metrics import percentile
from delivery.server import App, make_handler


def run(key, **kw):
    return Simulation(scenario_config(key, **kw)).run()


class TestModel(unittest.TestCase):
    def test_percentile(self):
        self.assertEqual(percentile([], 95), 0.0)
        self.assertAlmostEqual(percentile([1, 2, 3, 4], 50), 2.5)
        self.assertEqual(percentile(range(101), 95), 95)

    def test_same_seed_same_result(self):
        self.assertEqual(run("normal").summary(), run("normal").summary())
        self.assertNotEqual(run("normal").summary()["placed"], run("normal", seed=1).summary()["placed"])

    def test_every_order_is_accounted_for(self):
        for key in SCENARIOS:
            s = run(key).summary()
            closed = s["delivered"] + s["abandoned"] + s["declined"]
            self.assertEqual(s["placed"], closed + s["in_progress"], key)

    def test_capacity_limits_are_never_exceeded(self):
        sim = Simulation(scenario_config("surge", duration=0))
        for _ in range(200):
            sim.advance(1)
            self.assertLessEqual(sim.mediator.slots_used, sim.cfg.mediator_slots)
            self.assertLessEqual(sim.fleet.busy, sim.cfg.couriers)
            for s in sim.services.values():
                self.assertLessEqual(s.busy, s.workers)

    def test_normal_day_is_healthy(self):
        sim = run("normal")
        s = sim.summary()
        self.assertEqual((s["abandoned"], s["peak_queue"]), (0, 0))
        self.assertIsNone(sim.bottleneck()["key"])

    def test_surge_fills_the_mediator(self):
        m = run("surge").summary()
        self.assertGreater(m["abandoned"], 100)
        self.assertGreater(m["peak_queue"], 100)
        self.assertGreater(m["utilization"]["mediator"], 0.8)
        self.assertLess(m["utilization"]["payment"], 0.15)      # services stay mostly idle
        # sample the diagnosis while the surge is at its worst
        sim = Simulation(scenario_config("surge", duration=0)).advance(150)
        self.assertTrue(sim.bottleneck()["starved"])

    def test_more_slots_remove_the_queue(self):
        s, base = run("surge_scaled").summary(), run("surge").summary()
        self.assertEqual(s["placed"], base["placed"])           # same order stream
        self.assertEqual((s["abandoned"], s["peak_queue"]), (0, 0))
        self.assertGreater(s["throughput"], base["throughput"])

    def test_courier_shortage_is_named_as_root_cause(self):
        sim = Simulation(scenario_config("courier_shortage", duration=0)).advance(150)
        self.assertEqual(sim.bottleneck()["key"], "couriers")

    def test_declined_payment_cancels_order(self):
        s = Simulation(Config(duration=60, payment_fail=1.0)).run().summary()
        self.assertEqual(s["dispatched"], 0)
        self.assertGreater(s["declined"], 50)

    def test_live_parameters(self):
        sim = Simulation(scenario_config("surge", duration=0)).advance(120)
        self.assertGreater(len(sim.mediator.inbound), 0)
        sim.set_param("mediator_slots", 400)
        self.assertEqual(len(sim.mediator.inbound), 0)         # queue admitted at once
        self.assertEqual(sim.set_param("couriers", 99999), 1000)  # clamped to the maximum
        sim.set_param("arrival_rate", 1)
        self.assertEqual(sim.intake.rate, 1)                   # replaces the surge
        with self.assertRaises(KeyError):
            sim.set_param("seed", 3)

    def test_colleagues_only_know_the_mediator(self):
        sim = Simulation(Config(duration=0))
        self.assertIsInstance(sim.mediator, Mediator)
        for c in [*sim.services.values(), sim.fleet, sim.intake]:
            self.assertIsInstance(c, Colleague)
            self.assertIs(c.mediator, sim.mediator)
            others = [*sim.services.values(), sim.fleet, sim.intake]
            self.assertFalse(any(v is o for v in vars(c).values() for o in others))

    def test_compare_runs_every_scenario(self):
        res = compare(duration=60)
        self.assertEqual(list(res), list(SCENARIOS))
        self.assertEqual(list(compare(["normal"], duration=30)), ["normal"])


class TestServer(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = App("normal")
        cls.httpd = HTTPServer(("127.0.0.1", 0), make_handler(cls.app))
        cls.base = f"http://127.0.0.1:{cls.httpd.server_address[1]}"
        threading.Thread(target=cls.httpd.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()

    def call(self, path, body=None):
        data = None if body is None else json.dumps(body).encode()
        req = urllib.request.Request(self.base + path, data=data, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req) as r:
            raw = r.read()
            return json.loads(raw) if r.headers["Content-Type"].startswith("application/json") else raw

    def expect_400(self, path, body):
        with self.assertRaises(urllib.error.HTTPError) as cm:
            self.call(path, body)
        self.assertEqual(cm.exception.code, 400)
        cm.exception.close()

    def test_tick_reset_params(self):
        self.call("/api/reset", {"scenario": "normal"})
        st = self.call("/api/tick", {"seconds": 5})
        self.assertEqual(st["t"], 5)
        self.assertEqual(st["series_len"], 5)
        self.assertEqual(self.call("/api/params", {"couriers": 50}), {"couriers": 50})
        st = self.call("/api/reset", {"scenario": "surge"})
        self.assertEqual((st["t"], st["scenario"]), (0, "surge"))

    def test_bad_input_returns_400_and_changes_nothing(self):
        before = self.call("/api/state")
        self.expect_400("/api/tick", {"seconds": 999})
        self.expect_400("/api/params", {"couriers": 7, "seed": 1})
        self.expect_400("/api/params", {"couriers": "many"})
        self.expect_400("/api/reset", {"scenario": "nope"})
        after = self.call("/api/state")
        self.assertEqual((after["t"], after["scenario"], after["config"]), (before["t"], before["scenario"], before["config"]))

    def test_page_meta_and_compare(self):
        self.assertIn(b"Delivery Dispatch Simulator", self.call("/"))
        self.assertIn("surge", self.call("/api/meta")["scenarios"])
        self.assertEqual(list(self.call("/api/compare?scenarios=normal")), ["normal"])
        self.expect_400("/api/compare?scenarios=nope", None)


if __name__ == "__main__":
    unittest.main()
