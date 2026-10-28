"""The order: the message that the mediator passes between colleagues."""
from .config import STEPS, TRIP_TIME


class Order:
    __slots__ = ("id", "placed", "times", "pay_ok", "trip", "stage", "admitted", "dispatched")

    def __init__(self, oid, placed, rng):
        self.id = oid
        self.placed = placed
        # every random draw for an order happens here, from the arrival stream, so runs
        # that differ only in capacity see exactly the same orders (common random numbers)
        self.times = {k: max(m * 0.25, rng.gauss(m, s)) for k, (_, m, s) in STEPS.items()}
        self.trip = max(8.0, rng.gauss(*TRIP_TIME))
        self.pay_ok = rng.random()
        self.stage = "queued"
        self.admitted = self.dispatched = None
