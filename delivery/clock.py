"""Discrete-event clock: a priority queue of (time, callback) pairs."""
import heapq
import itertools


class Clock:
    def __init__(self):
        self.now = 0.0
        self._events = []
        self._seq = itertools.count()     # tie-breaker keeps same-time events in FIFO order
        self.on_tick = None               # called with the new time before each event runs

    def after(self, delay, fn, *args):
        heapq.heappush(self._events, (self.now + delay, next(self._seq), fn, args))

    def advance(self, seconds):
        """Run every event due in the next `seconds` of simulated time."""
        end = self.now + seconds
        while self._events and self._events[0][0] <= end:
            t, _, fn, args = heapq.heappop(self._events)
            self._move_to(t)
            fn(*args)
        self._move_to(end)

    def _move_to(self, t):
        if self.on_tick:
            self.on_tick(t)
        self.now = t
