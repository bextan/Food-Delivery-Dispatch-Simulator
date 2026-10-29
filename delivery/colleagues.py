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


class Service(Colleague):
    """A pool of workers with a FIFO queue (payment, kitchen, courier matching, notify).

    When a step finishes it sends the event "<key>_done" to the mediator."""

    def __init__(self, mediator, clock, key, workers):
        super().__init__(mediator, clock)
        self.key, self.workers = key, workers
        self.label = STEPS[key][0]
        self.busy = 0
        self.queue = deque()
        self.busy_time = 0.0       # integral of busy workers over time
        self._last = 0.0

    def account(self):
        now = self.clock.now
        self.busy_time += self.busy * (now - self._last)
        self._last = now

    def submit(self, order):
        order.stage = self.key
        self.queue.append(order)
        self._start_next()

    def _start_next(self):
        while self.queue and self.busy < self.workers:
            order = self.queue.popleft()
            self.account()
            self.busy += 1
            self.clock.after(order.times[self.key], self._finish, order)

    def _finish(self, order):
        self.account()
        self.busy -= 1
        self.mediator.notify(self, f"{self.key}_done", order)
        self._start_next()


class CourierFleet(Colleague):
    """The couriers. A courier is busy from assignment until the delivery is made.

    Sends "courier_assigned" when a courier takes an order and "delivered" when the
    trip ends."""

    def __init__(self, mediator, clock, cfg):
        super().__init__(mediator, clock)
        self.cfg = cfg
        self.busy = 0
        self.waiting = deque()

    @property
    def size(self):
        return self.cfg.couriers          # read live, so the size can change mid-run

    def request(self, order):
        if self.busy < self.size:
            self._assign(order)
        else:
            order.stage = "waiting_courier"
            self.waiting.append(order)

    def start_trip(self, order):
        self.clock.after(order.trip, self._trip_done, order)

    def assign_waiting(self):
        while self.waiting and self.busy < self.size:
            self._assign(self.waiting.popleft())

    def _assign(self, order):
        self.busy += 1
        self.mediator.notify(self, "courier_assigned", order)

    def _trip_done(self, order):
        self.busy -= 1
        self.mediator.notify(self, "delivered", order)
        self.assign_waiting()
