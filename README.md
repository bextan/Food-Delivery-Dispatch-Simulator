# Food Delivery Dispatch Simulator 

A small, readable simulator of a food delivery system built on the **mediator pattern**. It shows how the mediator
coordinates every order, when its slots become the bottleneck, and how much capacity it needs to keep up. It has a
live web dashboard and a command line tool.

It uses only the Python 3.10+ standard library. There is nothing to install.

```bash
python main.py              # opens the dashboard at http://127.0.0.1:8770
```

Documentation in `docs/`:

* [SRS.doc](docs/SRS.doc): software requirements specification on the IEEE template.
* [SRS_Simple.doc](docs/SRS_Simple.doc): a shorter, plain-language SRS (purpose, scope, requirements).
* [ADR.doc](docs/ADR.doc): architecture decision records (why mediator, why the standard library, and so on).

## Architecture: the mediator pattern

```
    OrderIntake  ─┐
    Payment      ─┤
    Kitchen      ─┼──►  OrderMediator   (every routing decision lives here)
    Courier match─┤
    Notify       ─┤
    CourierFleet ─┘
```

* **Mediator** (`delivery/mediator.py`): `Mediator` is the abstract interface with one method,
  `notify(sender, event, order)`. `OrderMediator` implements it and holds the whole workflow:

  | event | what the mediator does |
  |---|---|
  | `order_placed` | put the order in the inbound queue; admit it when a slot is free and send it to Payment |
  | `payment_done` | declined → cancel the order; otherwise send it to Kitchen |
  | `kitchen_done` | send it to Courier match |
  | `courier_done` | ask the CourierFleet for a courier |
  | `courier_assigned` | send it to Notify |
  | `notify_done` | order dispatched: free the slot, start the courier's trip |
  | `delivered` | order complete |

* **Colleagues** (`delivery/colleagues.py`): `OrderIntake`, four `Service`s and `CourierFleet`. Each does one job and
  holds a reference only to the mediator. When it finishes, it calls `mediator.notify(...)`. No colleague calls
  another colleague, so a step can be changed or reordered by editing the mediator alone.
* **Order** (`delivery/order.py`): the message passed around.
* **Metrics** (`delivery/metrics.py`): watches and reports. It never changes the workflow.
* **Simulation** (`delivery/simulation.py`): creates the mediator and colleagues, connects them, and runs them on one
  discrete-event `Clock` (`delivery/clock.py`).

## How it works

* The mediator holds one slot for an order from admission until the "courier on the way" notification is sent.
  When every slot is taken, new orders wait in the inbound queue. A customer whose order waits there longer than
  `patience` seconds gives up.
* Each service has a fixed number of workers, and extra work waits in its queue. After courier matching the order needs
  a free courier. If none is free, it waits and keeps its mediator slot.
* 2% of payments are declined, which cancels the order.
* All random values for an order are drawn when it arrives, so runs with the same seed see identical orders.
* Courier trips are time-compressed (about 25 simulated seconds) so the fleet stays a readable size.
* The latencies, trip times and failure rate are illustrative, not measured from a real platform.

## Dashboard

* **Run controls:** start/pause, reset, scenario, speed (1×–20×).
* **Live settings:** orders per second, mediator slots, couriers and customer patience. These apply mid-run.
* **KPI tiles:** dispatches per second, inbound queue, dispatch p95, delivered, abandoned and revenue lost, each with an
  OK/High/Critical status.
* **Pipeline:** how busy each part is right now, plus an automatic bottleneck diagnosis that flags the
  *starvation paradox* (the mediator is full while the services behind it are idle).
* **Couriers:** a busy/idle grid of the fleet.
* **Charts:** queues, rolling dispatch time (p50/p95) and utilisation, with hover tooltips.
* **Compare scenarios:** runs every scenario through the mediator and shows the results side by side.

## Command line

```bash
python main.py scenarios
python main.py run -s surge
python main.py run -s surge --json
python main.py compare                     # every scenario
python main.py compare -s surge surge_scaled
python main.py serve --port 8770 --no-browser
```

Results from `compare -s surge surge_scaled` (same orders, 30 vs 90 mediator slots):

```
                                     surge      surge_scaled
  orders placed                       2236              2236
  delivered                           1382              1928
  abandoned                            375                 0
  dispatches per second               5.12              7.14
  dispatch time p95                  36.0s              6.5s
  peak inbound queue                   276                 0
```

## Scenarios

| key | what happens |
|---|---|
| `normal` | 2 orders/s. Everything keeps up. |
| `surge` | Demand jumps from 2 to 9 orders/s at t=60s. The mediator's 30 slots run out. |
| `surge_scaled` | The same surge with 90 slots. The queue disappears. |
| `courier_shortage` | 3 orders/s with only 60 couriers. Orders wait for a courier while holding mediator slots. |

## Files

```
main.py                    entry point: dashboard and command line
delivery/mediator.py       Mediator interface and OrderMediator (the workflow)
delivery/colleagues.py     OrderIntake, Service, CourierFleet
delivery/order.py          Order
delivery/metrics.py        statistics, summary, bottleneck diagnosis
delivery/simulation.py     wires mediator + colleagues; scenario comparison
delivery/clock.py          discrete-event clock
delivery/config.py         settings, step timings, scenarios
delivery/server.py         JSON API and the dashboard page
delivery/web/index.html    the dashboard (HTML, CSS and JS in one file)
tests/test_delivery.py     python -m unittest discover -s tests
docs/SRS.doc               software requirements specification (IEEE template)
docs/SRS_Simple.doc        simplified SRS
docs/ADR.doc               architecture decision records
```

### HTTP API
`GET /api/state?since=N` · `GET /api/meta` · `GET /api/compare[?scenarios=surge,surge_scaled]` ·
`POST /api/tick {seconds, since}` · `POST /api/reset {scenario}` · `POST /api/params {name: value}`
