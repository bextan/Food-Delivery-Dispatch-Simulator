"""Settings, step timings and the predefined scenarios."""
from dataclasses import asdict, dataclass, replace

# step key -> (label, mean seconds, std seconds)
STEPS = {
    "payment": ("Payment", 0.3, 0.08),
    "kitchen": ("Kitchen", 1.5, 0.4),
    "courier": ("Courier match", 3.0, 0.8),
    "notify": ("Notify", 0.2, 0.05),
}
TRIP_TIME = (25.0, 6.0)          # courier busy time per delivery (time-compressed)
ORDER_VALUE = 25.0               # dollars, for the revenue figure


@dataclass
class Config:
    seed: int = 7
    duration: float = 300.0      # seconds of simulated time
    arrival_rate: float = 2.0    # orders per second
    surge_rate: float = 0.0      # if > 0, the arrival rate from `surge_at` on
    surge_at: float = 60.0
    mediator_slots: int = 30
    payment_workers: int = 20
    kitchen_workers: int = 25
    courier_workers: int = 60
    notify_workers: int = 20
    couriers: int = 100
    patience: float = 30.0       # seconds a customer waits in the inbound queue
    payment_fail: float = 0.02   # probability that a payment is declined

    def to_dict(self):
        return asdict(self)


# Values the user may change while the simulation runs: name -> (type, min, max)
LIVE_PARAMS = {
    "arrival_rate": (float, 0.1, 20.0),
    "mediator_slots": (int, 1, 500),
    "couriers": (int, 1, 1000),
    "patience": (float, 1.0, 600.0),
}

SCENARIOS = {
    "normal": ("Normal day", "2 orders/s. Everything keeps up.", {}),
    "surge": ("Demand surge", "Demand jumps from 2 to 9 orders/s at t=60s. The mediator's 30 slots run out.",
              dict(surge_rate=9.0, couriers=320)),
    "surge_scaled": ("Surge, bigger mediator", "The same surge with 90 slots. The queue disappears.",
                     dict(surge_rate=9.0, couriers=320, mediator_slots=90)),
    "courier_shortage": ("Courier shortage", "3 orders/s but only 60 couriers. Orders wait for couriers while holding slots.",
                         dict(arrival_rate=3.0, couriers=60)),
}


def scenario_config(key, **overrides):
    if key not in SCENARIOS:
        raise KeyError(f"unknown scenario {key!r}; choose from {', '.join(SCENARIOS)}")
    return replace(Config(), **{**SCENARIOS[key][2], **overrides})
