"""The mediator: the single place where the order workflow is defined.

    order_placed     -> wait for a free slot in the inbound queue, then send to Payment
    payment_done     -> declined? cancel the order : send to Kitchen
    kitchen_done     -> send to Courier match
    courier_done     -> ask the CourierFleet for a courier
    courier_assigned -> send to Notify
    notify_done      -> order dispatched: free the slot, start the courier's trip
    delivered        -> order complete

The mediator holds one of its `mediator_slots` for every order from admission until the
"courier on the way" notification is sent. When every slot is taken, new orders wait in
the inbound queue; a customer who waits longer than `patience` seconds gives up.
"""
from abc import ABC, abstractmethod
from collections import deque


class Mediator(ABC):
    @abstractmethod
    def notify(self, sender, event, order):
        """Called by a colleague when something happened to an order."""


class OrderMediator(Mediator):
    def __init__(self, clock, cfg, metrics):
        self.clock, self.cfg, self.metrics = clock, cfg, metrics
        self.inbound = deque()             # orders waiting for a mediator slot
        self.slots_used = 0
        self.saturated = False
        # colleagues are attached by `connect` once they exist
        self.payment = self.kitchen = self.courier_match = self.notifier = self.fleet = None

    def connect(self, payment, kitchen, courier_match, notifier, fleet):
        self.payment, self.kitchen = payment, kitchen
        self.courier_match, self.notifier, self.fleet = courier_match, notifier, fleet

    # ---- the workflow ------------------------------------------------------------
    def notify(self, sender, event, order):
        if event == "order_placed":
            self.metrics.placed(order)
            self.inbound.append(order)
            self.clock.after(self.cfg.patience, self._check_patience, order)
            self.admit()
        elif event == "payment_done":
            if order.pay_ok < self.cfg.payment_fail:
                self._release_slot()
                self.metrics.close(order, "declined")
            else:
                self.kitchen.submit(order)
        elif event == "kitchen_done":
            self.courier_match.submit(order)
        elif event == "courier_done":
            self.fleet.request(order)
        elif event == "courier_assigned":
            self.notifier.submit(order)
        elif event == "notify_done":
            order.dispatched = self.clock.now
            order.stage = "delivering"
            self.metrics.dispatched(order)
            self._release_slot()
            self.fleet.start_trip(order)
        elif event == "delivered":
            self.metrics.delivered(order)
        else:
            raise ValueError(f"unknown event {event!r} from {type(sender).__name__}")

    # ---- admission control -------------------------------------------------------
    def admit(self):
        """Move orders from the inbound queue into free slots."""
        while self.inbound and self.slots_used < self.cfg.mediator_slots:
            order = self.inbound.popleft()
            self.slots_used += 1
            order.admitted = self.clock.now
            self.metrics.admitted(order)
            self.payment.submit(order)
        self.saturated = bool(self.inbound)   # orders left over means every slot is taken

    def _release_slot(self):
        self.slots_used -= 1
        self.admit()

    def _check_patience(self, order):
        if order.stage == "queued":
            self.inbound.remove(order)
            self.metrics.close(order, "abandoned")
