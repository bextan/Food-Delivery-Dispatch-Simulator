"""Builds the mediator and its colleagues, and runs them on one clock.

    OrderIntake ─┐
    Payment     ─┤
    Kitchen     ─┼──►  OrderMediator  (all routing decisions live here)
    CourierMatch─┤
    Notify      ─┤
    CourierFleet─┘
"""
import random

from .clock import Clock
from .colleagues import CourierFleet, OrderIntake, Service
from .config import LIVE_PARAMS, SCENARIOS, STEPS, Config, scenario_config
from .mediator import OrderMediator
from .metrics import Metrics


class Simulation:
    def __init__(self, cfg=None):
        self.cfg = cfg or Config()
        self.clock = Clock()
        self.metrics = Metrics(self.clock, self.cfg)
        self.mediator = OrderMediator(self.clock, self.cfg, self.metrics)
        self.services = {k: Service(self.mediator, self.clock, k, getattr(self.cfg, f"{k}_workers"))
                         for k in STEPS}
        self.fleet = CourierFleet(self.mediator, self.clock, self.cfg)
        self.intake = OrderIntake(self.mediator, self.clock, self.cfg, random.Random(self.cfg.seed))
        s = self.services
        self.mediator.connect(s["payment"], s["kitchen"], s["courier"], s["notify"], self.fleet)
        self.clock.on_tick = self.metrics.accumulate
        self.intake.start()
        self.metrics.watch(self.mediator, self.services, self.fleet, self.intake)

    @property
    def now(self):
        return self.clock.now

    def advance(self, seconds):
        """Run the simulation forward by `seconds` of simulated time."""
        self.clock.advance(seconds)
        return self

    def run(self):
        return self.advance(self.cfg.duration - self.clock.now)

    def summary(self):
        return self.metrics.summary()

    def bottleneck(self):
        return self.metrics.bottleneck()

    def set_param(self, name, value):
        """Change a setting while the simulation runs."""
        if name not in LIVE_PARAMS:
            raise KeyError(f"{name!r} cannot be changed while running")
        kind, lo, hi = LIVE_PARAMS[name]
        value = min(hi, max(lo, kind(value)))
        setattr(self.cfg, name, value)
        if name == "arrival_rate":
            self.cfg.surge_rate = 0.0        # a manual rate replaces the scenario's surge
        elif name == "mediator_slots":
            self.mediator.admit()
        elif name == "couriers":
            self.fleet.assign_waiting()
        return value

    def state(self, since=0):
        """Everything the dashboard needs, as JSON-friendly data."""
        m = self.mediator
        return {
            "t": round(self.clock.now, 2),
            "config": self.cfg.to_dict(),
            "rate": self.intake.rate,
            "queue": len(m.inbound),
            "slots_used": m.slots_used,
            "couriers_busy": self.fleet.busy,
            "waiting_for_courier": len(self.fleet.waiting),
            "services": {k: {"label": s.label, "busy": s.busy, "workers": s.workers, "queue": len(s.queue)}
                         for k, s in self.services.items()},
            "summary": self.summary(),
            "bottleneck": self.bottleneck(),
            "series": self.metrics.series[since:],
            "series_len": len(self.metrics.series),
        }


def compare(scenarios=None, seed=7, duration=300.0):
    """Run several scenarios through the mediator with the same seed, side by side."""
    out = {}
    for key in scenarios or SCENARIOS:
        sim = Simulation(scenario_config(key, seed=seed, duration=duration)).run()
        out[key] = {"summary": sim.summary(), "bottleneck": sim.bottleneck()["text"]}
    return out
