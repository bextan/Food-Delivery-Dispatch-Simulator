# Software Requirements Specification

**Food Delivery Dispatch Simulator** · Version 1.0 · Prepared by Bexultan · Software Architecture Course · 3 November 2026

## Revision History

| Date | Author | Version | Reason for change |
|---|---|---|---|
| 3 November 2026 | Bexultan | 1.0 | First version, based on IEEE Std 830 |

## 1. Introduction

### 1.1 Purpose
This document says what the Food Delivery Dispatch Simulator must do. The program simulates a food delivery service in which one central part, the **mediator**, controls every order. It shows how the system behaves under heavy load and what happens when the mediator runs out of capacity.

### 1.2 Document Conventions
Requirement codes: `REQ` functions, `UI` screen, `SI` software interfaces, `NFR` quality. "Must" means mandatory. Times are simulated seconds unless stated otherwise.

### 1.3 Audience
Students, teachers and reviewers of the software architecture course, and developers who change the code. Everyone should read sections 1–2; developers should also read 3–4.

### 1.4 Product Scope
A learning tool that runs on one computer, with a web dashboard and a command line. It handles no real orders, payments or restaurants. All times and rates are illustrative, not measured from a real company.

### 1.5 References
- IEEE Std 830-1998, *Recommended Practice for Software Requirements Specifications*.
- Gamma, Helm, Johnson, Vlissides, *Design Patterns* (1994): Mediator pattern.
- Project files: `README.md`, `docs/ADR.md`.

## 2. Overall Description

### 2.1 Product Perspective
A new standalone product. Six parts (**colleagues**) do the work: Order Intake, Payment, Kitchen, Courier Match, Notify and Courier Fleet. They never call each other. Each reports to the `OrderMediator`, which decides the next step. The mediator has a limited number of **slots**; an order holds one from admission until the customer is told a courier is on the way. When all slots are busy, new orders wait in a queue.

### 2.2 Product Functions
- Simulate orders through payment, kitchen, courier match, notification and delivery.
- Let the user pick a scenario and change settings while it runs.
- Show live numbers, charts and the current bottleneck.
- Compare all scenarios side by side and run from the command line.

### 2.3 User Classes
| User | Uses | Needs |
|---|---|---|
| Student / presenter | Dashboard | No programming knowledge |
| Teacher / reviewer | Command line, code | Exact, repeatable numbers |
| Developer | Code, tests | Basic Python |

### 2.4 Operating Environment
Windows, macOS or Linux with Python 3.10+; any modern browser (Chrome, Edge, Firefox, Safari). Runs only on the user's computer at `http://127.0.0.1:8770`.

### 2.5 Constraints
- Python standard library only; nothing to install.
- Dashboard is one HTML file with plain JavaScript and no external libraries.
- Parts may talk only to the mediator.
- Entry point is `main.py`.

### 2.6 User Documentation
`README.md` (how to start and use), this SRS and `docs/ADR.md` (design decisions).

### 2.7 Assumptions and Dependencies
- Orders arrive as a Poisson process at a set average rate; each step takes a random time around a set average.
- Courier trips are shortened to about 25 s to keep the fleet small.
- 2% of payments fail; a lost order is valued at $25.

## 3. External Interface Requirements

### 3.1 User Interface
| ID | Requirement |
|---|---|
| UI-1 | Start/Pause and Reset buttons, a scenario list and a speed list (1×–20×). |
| UI-2 | Sliders for orders per second, mediator slots, couriers and customer patience. |
| UI-3 | Six tiles: dispatches per second, queue, dispatch time (p95), delivered, abandoned, money lost; status colour (green/yellow/red) where meaningful. |
| UI-4 | Utilisation of each part (queue, slots, services, couriers) and a short text naming the bottleneck. |
| UI-5 | A busy/free courier grid and three charts: queues, dispatch time, utilisation. |
| UI-6 | A "Compare scenarios" table. |
| UI-7 | Usable on phone and desktop screens. |

### 3.2 Hardware Interfaces
None.

### 3.3 Software Interfaces (JSON over HTTP)
| ID | Endpoint | Purpose |
|---|---|---|
| SI-1 | `GET /api/state` | Current simulation state. |
| SI-2 | `GET /api/meta` | Scenario list and limits of each setting. |
| SI-3 | `GET /api/compare` | Results of all (or selected) scenarios. |
| SI-4 | `POST /api/tick` | Advance the simulation by up to 10 s. |
| SI-5 | `POST /api/reset` | Restart with a chosen scenario. |
| SI-6 | `POST /api/params` | Change settings while running. |
| SI-7 | any | Wrong input returns HTTP 400 and changes nothing. |

### 3.4 Communications Interfaces
HTTP on the same computer. While running, the page calls `/api/tick` four times per second.

## 4. System Features

### 4.1 Order Processing by the Mediator (priority: High)
**Flow:** order placed → waits for a free slot → Payment → Kitchen → Courier Match → free courier assigned → Notify → courier delivers.
**Exceptions:** a failed payment cancels the order; with no free courier the order waits and keeps its slot; a customer who waits too long for a slot leaves.

| ID | Requirement |
|---|---|
| REQ-1 | Create orders at the chosen rate; in surge scenarios raise the rate at the set time. |
| REQ-2 | Send each order through payment, kitchen, courier match and notify, in this order. |
| REQ-3 | Never work on more orders than there are slots. |
| REQ-4 | Orders without a slot wait in a first-come, first-served queue. |
| REQ-5 | An order waiting longer than the patience time is counted as abandoned. |
| REQ-6 | A service never works on more orders than it has workers; extra orders wait in its own queue. |
| REQ-7 | A failed payment cancels the order and frees its slot. |
| REQ-8 | A courier is busy from assignment until delivery; busy couriers never exceed the fleet size. |
| REQ-9 | Parts communicate only through the mediator. |

### 4.2 Scenarios and Live Settings (priority: High)
Scenarios: **Normal day** (2 orders/s, keeps up); **Demand surge** (2 → 9 orders/s at 60 s, 30 slots not enough); **Surge with a bigger mediator** (same surge, 90 slots); **Courier shortage** (3 orders/s, 60 couriers).

| ID | Requirement |
|---|---|
| REQ-10 | The user can choose any of the four scenarios. |
| REQ-11 | While running, the user can change orders/s (0.1–20), slots (1–500), couriers (1–1000) and patience (1–600 s). Out-of-range values are moved to the nearest limit. |
| REQ-12 | Changing the order rate by hand stops the scenario's surge. |
| REQ-13 | Adding slots or couriers lets waiting orders continue at once. |

### 4.3 Statistics and Bottleneck Detection (priority: High)

| ID | Requirement |
|---|---|
| REQ-14 | Every simulated second, record queue length, slots in use, dispatches per second, dispatch time (p50/p95 over the last 20 s) and utilisation of each part. |
| REQ-15 | The summary shows orders placed, dispatched, delivered, abandoned, declined, success rate, dispatch time, biggest queue and money lost. |
| REQ-16 | Name the bottleneck: "none" when every part is under 80% busy; "couriers" when they are at least 95% busy and orders wait for them; "starvation paradox" when the mediator is at least 95% full while the services are under 60% busy. |

### 4.4 Scenario Comparison and Command Line (priority: Medium)

| ID | Requirement |
|---|---|
| REQ-17 | Run every chosen scenario for 300 s with the same random seed and show results side by side. |

## 5. Other Nonfunctional Requirements

### 5.1 Performance
- NFR-1: A full 300 s scenario finishes in under 2 seconds on a normal laptop.
- NFR-2: The dashboard stays smooth at 20× speed.

### 5.2 Safety
None. It is a simulation and cannot cause real-world harm.

### 5.3 Security
- NFR-3: The server accepts connections only from this computer (127.0.0.1).
- NFR-4: Wrong or out-of-range input is rejected.

### 5.4 Quality Attributes
- NFR-5 **Repeatable:** the same scenario and seed always give the same results.
- NFR-6 **Changeable:** the order flow changes by editing only `mediator.py`.
- NFR-7 **Testable:** automatic tests cover the simulation and the API.
- NFR-8 **Easy to run:** only Python 3.10+ is needed.

### 5.5 Business Rules
Every order ends as exactly one of: delivered, abandoned or declined, or is still in progress.

## 6. Other Requirements
None.

## Appendix A: Glossary
| Term | Meaning |
|---|---|
| Mediator | Central part that controls the order flow. |
| Colleague | A part that does one job and talks only to the mediator. |
| Slot | One unit of mediator capacity; one order in progress uses one. |
| Dispatch time | From placing an order until the customer is told a courier is on the way. |
| p50 / p95 | Time that 50% / 95% of orders beat. |
| Bottleneck | The part that limits overall speed. |
| Starvation paradox | The mediator is full while the services behind it have little work. |

## Appendix B: Analysis Models
**Code structure (one file per mediator-pattern role):** `main.py` (entry), `delivery/mediator.py` (Mediator, OrderMediator), `colleagues.py` (OrderIntake, Service, CourierFleet), `order.py`, `metrics.py`, `simulation.py`, `clock.py`, `config.py`, `server.py` and `web/index.html`.

**Example results** (seed 7, 300 s):

| Scenario | Slots | Delivered | Abandoned | p95 dispatch |
|---|---|---|---|---|
| Demand surge | 30 | 1382 of 2236 | 375 | 36.0 s |
| Surge, bigger mediator | 90 | 1928 | 0 | 6.5 s |

