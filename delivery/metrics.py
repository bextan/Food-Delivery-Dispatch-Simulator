"""Statistics: counters, latencies, per-second samples, summary and bottleneck diagnosis.

Metrics only observes. It never changes the workflow."""
from collections import deque

from .config import ORDER_VALUE, STEPS


def percentile(values, p):
    """Linear-interpolated percentile; 0 for an empty list."""
    v = sorted(values)
    if not v:
        return 0.0
    k = (len(v) - 1) * p / 100
    lo = int(k)
    hi = min(lo + 1, len(v) - 1)
    return v[lo] + (v[hi] - v[lo]) * (k - lo)


class Metrics:
    def __init__(self, clock, cfg):
        self.clock, self.cfg = clock, cfg
        self.counts = dict(placed=0, dispatched=0, delivered=0, abandoned=0, declined=0)
        self.active = {}
        self.dispatch_times, self.queue_waits, self.delivery_times = [], [], []
        self.series = []                     # one row per simulated second
        self._recent = deque()               # (time, dispatch latency) for rolling stats
        self._slot_time = self._courier_time = 0.0
        self._last_acc = 0.0
        self._last_sample = {k: 0.0 for k in STEPS}
        self._last_sample_acc = (0.0, 0.0)

    def watch(self, mediator, services, fleet, intake):
        self.mediator, self.services, self.fleet, self.intake = mediator, services, fleet, intake
        self.clock.after(1.0, self._sample)

    # ---- recording (called by the mediator) ------------------------------------------
    def placed(self, order):
        self.active[order.id] = order
        self.counts["placed"] += 1

    def admitted(self, order):
        self.queue_waits.append(order.admitted - order.placed)

    def dispatched(self, order):
        latency = order.dispatched - order.placed
        self.dispatch_times.append(latency)
        self._recent.append((self.clock.now, latency))
        self.counts["dispatched"] += 1

    def delivered(self, order):
        self.delivery_times.append(self.clock.now - order.placed)
        self.close(order, "delivered")

    def close(self, order, outcome):
        order.stage = outcome
        self.counts[outcome] += 1
        self.active.pop(order.id, None)

    def accumulate(self, t):
        """Integrate busy slots and couriers over time (called by the clock)."""
        dt = t - self._last_acc
        self._slot_time += self.mediator.slots_used * dt
        self._courier_time += self.fleet.busy * dt
        self._last_acc = t

    # ---- per-second samples --------------------------------------------------------
    def _sample(self):
        t = self.clock.now
        med, fleet = self.mediator, self.fleet
        while self._recent and self._recent[0][0] < t - 20:
            self._recent.popleft()
        recent = [x for _, x in self._recent]
        last_t = self.series[-1]["t"] if self.series else 0.0
        dt = max(t - last_t, 1e-9)
        util = {}
        for k, s in self.services.items():
            s.account()
            util[k] = (s.busy_time - self._last_sample[k]) / (dt * max(s.workers, 1))
            self._last_sample[k] = s.busy_time
        slot_prev, courier_prev = self._last_sample_acc
        util["mediator"] = (self._slot_time - slot_prev) / (dt * self.cfg.mediator_slots)
        util["couriers"] = (self._courier_time - courier_prev) / (dt * self.cfg.couriers)
        self._last_sample_acc = (self._slot_time, self._courier_time)
        dispatched_before = self.series[-1]["dispatched"] if self.series else 0
        self.series.append({
            "t": round(t, 3),
            "rate": self.intake.rate,
            "queue": len(med.inbound),
            "slots": med.slots_used,
            "wait_courier": len(fleet.waiting),
            "throughput": (self.counts["dispatched"] - dispatched_before) / dt,
            "p50": percentile(recent, 50),
            "p95": percentile(recent, 95),
            "dispatched": self.counts["dispatched"],
            "util": {k: round(min(v, 1.0), 4) for k, v in util.items()},
        })
        self.clock.after(1.0, self._sample)

    # ---- reports ---------------------------------------------------------------------
    def bottleneck(self):
        """Name the busiest resource right now, and flag the starvation paradox:
        the mediator is full while the services behind it are mostly idle."""
        if not self.series:
            return {"key": None, "text": "Not started yet.", "starved": False}
        u = self.series[-1]["util"]
        names = {"mediator": "Mediator slots", "couriers": "Couriers", **{k: v[0] for k, v in STEPS.items()}}
        key = max(u, key=u.get)
        busiest_service = max(u[k] for k in STEPS)
        couriers_short = u["couriers"] >= 0.95 and self.fleet.waiting
        starved = (u["mediator"] >= 0.95 and busiest_service < 0.6 and bool(self.mediator.inbound)
                   and not couriers_short)
        if u[key] < 0.8:
            text = "No bottleneck. Every resource has spare capacity."
            key = None
        elif couriers_short:
            key = "couriers"
            text = (f"Couriers: all busy, {len(self.fleet.waiting)} orders waiting for one."
                    " Those orders keep their mediator slots, so the mediator fills up too.")
        elif starved:
            text = (f"Mediator slots are full while the busiest service is only "
                    f"{busiest_service:.0%} busy. Orders queue for the mediator, not for real work.")
        else:
            text = f"{names[key]}: {u[key]:.0%} busy."
        return {"key": key, "text": text, "starved": starved}

    def summary(self):
        c, d = self.counts, self.dispatch_times
        t = max(self.clock.now, 1e-9)
        util = {}
        for k, s in self.services.items():
            s.account()
            util[k] = round(s.busy_time / (t * max(s.workers, 1)), 4)
        util["mediator"] = round(self._slot_time / (t * self.cfg.mediator_slots), 4)
        util["couriers"] = round(self._courier_time / (t * self.cfg.couriers), 4)
        closed = c["delivered"] + c["abandoned"] + c["declined"]
        return {
            "time": round(self.clock.now, 1),
            **c,
            "in_progress": len(self.active),
            "success_rate": round(c["delivered"] / closed, 4) if closed else 0.0,
            "throughput": round(c["dispatched"] / t, 3),
            "dispatch_p50": round(percentile(d, 50), 2),
            "dispatch_p95": round(percentile(d, 95), 2),
            "queue_wait_p95": round(percentile(self.queue_waits, 95), 2),
            "delivery_p50": round(percentile(self.delivery_times, 50), 2),
            "peak_queue": max((r["queue"] for r in self.series), default=0),
            "revenue_lost": round((c["abandoned"] + c["declined"]) * ORDER_VALUE, 2),
            "utilization": util,
        }
