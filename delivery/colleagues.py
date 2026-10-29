"""Colleagues of the mediator pattern.

Each colleague does one job and knows only the mediator. When it finishes something it
calls `mediator.notify(self, event, order)` and the mediator decides what happens next.
No colleague ever calls another colleague directly.
"""
from collections import deque

from .config import STEPS
from .order import Order


class Colleague:
    def __init__(self, mediator, clock):
        self.mediator = mediator
        self.clock = clock


class OrderIntake(Colleague):
    """Customers placing orders: a Poisson arrival stream."""

    def __init__(self, mediator, clock, cfg, rng):
        super().__init__(mediator, clock)
        self.cfg, self.rng = cfg, rng
        self._next_id = 1

    @property
    def rate(self):
        c = self.cfg
        return c.surge_rate if c.surge_rate and self.clock.now >= c.surge_at else c.arrival_rate

    def start(self):
        self.clock.after(self.rng.expovariate(self.rate), self._arrive)

    def _arrive(self):
        order = Order(self._next_id, self.clock.now, self.rng)
        self._next_id += 1
        self.mediator.notify(self, "order_placed", order)
        self.start()
