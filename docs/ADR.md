# Architecture Decision Records

**Food Delivery Dispatch Simulator** · Version 1.0 · Prepared by Bexultan · 3 November 2026

Each record gives the situation (context), the decision, its consequences and the options rejected. The format follows Michael Nygard's ADR template.

| ADR | Decision | Status | Date |
|---|---|---|---|
| [001](#adr-001-use-the-mediator-pattern-for-the-order-workflow) | Use the mediator pattern for the order workflow | Accepted | 3 November 2026 |
| [002](#adr-002-mediator-holds-a-slot-per-order-until-the-customer-is-notified) | Mediator holds a slot per order until the customer is notified | Accepted | 3 November 2026 |
| [003](#adr-003-organise-the-code-by-mediator-pattern-roles) | Organise the code by mediator-pattern roles | Accepted | 3 November 2026 |
| [004](#adr-004-discrete-event-simulation-with-a-custom-clock) | Discrete-event simulation with a custom clock | Accepted | 3 November 2026 |
| [005](#adr-005-browser-driven-clock-and-a-single-file-dashboard) | Browser-driven clock and a single-file dashboard | Accepted | 3 November 2026 |
| [006](#adr-006-use-only-the-python-standard-library) | Use only the Python standard library | Accepted | 3 November 2026 |

---

## ADR-001: Use the mediator pattern for the order workflow
**Status:** Accepted · **Date:** 3 November 2026

**Context.** An order passes through payment, kitchen, courier matching and customer notification. Some outcomes change the flow (a declined payment cancels the order; no free courier makes it wait). The project teaches the mediator pattern, so the workflow must be easy to find, read and change.

**Decision.** All routing is done by one `OrderMediator`. Components (colleagues) report events with `notify(sender, event, order)` and the mediator decides the next step. A broker (choreography) topology is not part of the project; the comparison panel compares scenarios instead.

**Consequences**
- (+) The whole workflow is in one place and reads like the business process.
- (+) Error handling (declined payment) and waiting rules are central and easy to change.
- (+) One pattern makes the project easier to present and grade.
- (−) The mediator is a central load point; under a surge it becomes the bottleneck (which the simulator shows).
- (−) The project no longer shows how a broker behaves on the same orders.

**Alternatives considered**
- *Broker / choreography:* each service passes the order on. Scales better but spreads the workflow across services; rejected to keep the focus.
- *Keep both topologies:* more code and a split message; rejected.

## ADR-002: Mediator holds a slot per order until the customer is notified
**Status:** Accepted · **Date:** 3 November 2026

**Context.** A real orchestrator has limited capacity (threads, connections, workflow instances). The simulator must show what happens when that capacity runs out.

**Decision.** The mediator has `mediator_slots` slots. An order takes one when admitted and frees it after the "courier on the way" notification, or when payment is declined. Orders without a slot wait in a first-in, first-out inbound queue and are abandoned after `patience` seconds. Slots can be changed while running.

**Consequences**
- (+) Shows the starvation paradox: the mediator is full while the services behind it are idle.
- (+) Gives a clear capacity-planning lesson: 30 slots fail the surge, 90 slots handle it.
- (−) Orders waiting for a courier keep their slot, which couples courier shortage to mediator capacity. This is intentional but must be explained to users.

**Alternatives considered**
- *Release the slot after each step:* hides the bottleneck the project is meant to show.
- *Unlimited mediator capacity:* no capacity lesson at all.

## ADR-003: Organise the code by mediator-pattern roles
**Status:** Accepted · **Date:** 3 November 2026

**Context.** A reader should see the pattern from the file list, and changing the workflow should touch as few files as possible.

**Decision.** One module per role: `mediator.py` (abstract `Mediator` and `OrderMediator`), `colleagues.py` (`OrderIntake`, `Service`, `CourierFleet`), `order.py` (the message), `metrics.py` (observer only), `simulation.py` (wiring), `clock.py` and `config.py`. Colleagues hold a reference only to the mediator; a unit test checks this.

**Consequences**
- (+) The structure matches the GoF diagram, so the pattern is visible at a glance.
- (+) Changing the flow means editing only `mediator.py`.
- (+) Statistics are separate from the workflow and cannot change it.
- (−) More files to navigate than a single-file version.

**Alternatives considered**
- *One model file:* shorter, but hides the pattern.
- *One file per service class:* too fine-grained for four nearly identical services.

## ADR-004: Discrete-event simulation with a custom clock
**Status:** Accepted · **Date:** 3 November 2026

**Context.** The simulator must run minutes of activity in a fraction of a second and give the same result every time.

**Decision.** A discrete-event clock: a priority queue (`heapq`) of `(time, sequence, callback)`. The simulation jumps from event to event. All random values for an order are drawn from one seeded generator when the order arrives.

**Consequences**
- (+) A 300-second scenario runs in well under a second.
- (+) Fully reproducible: the same seed gives identical orders, so scenarios that differ only in capacity are directly comparable.
- (−) The clock and worker queues are written by hand (about 60 lines) instead of using a library.

**Alternatives considered**
- *SimPy:* the standard library for this, but needs installing and hides the event loop.
- *Real time with threads:* slow, not reproducible and harder to test.

## ADR-005: Browser-driven clock and a single-file dashboard
**Status:** Accepted · **Date:** 3 November 2026

**Context.** The dashboard must show the simulation live, support pause and speed changes, and stay simple.

**Decision.** The server has no background thread. While running, the page calls `POST /api/tick` every 250 ms with the simulated seconds to advance (speed × 0.25 s, at most 10 s) and receives only the new samples. The whole dashboard is one file, `web/index.html`.

**Consequences**
- (+) No threads or locks; pausing is simply not calling tick.
- (+) Speed is a client setting; the server stays stateless apart from the simulation.
- (+) One file is easy to read and serve.
- (−) The simulation advances only while a browser tab is open and running.
- (−) Only one browser at a time can control the simulation.

**Alternatives considered**
- *Server thread with WebSockets or server-sent events:* more complex, needs locking.
- *Front-end framework (React, Vue):* needs a build step.
