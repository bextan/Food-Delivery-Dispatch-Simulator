"""Entry point.

    python main.py                          open the web dashboard
    python main.py run -s surge             run one scenario and print a report
    python main.py compare                  run every scenario side by side
    python main.py scenarios                list the scenarios
"""
import argparse
import json
import sys

from delivery.config import SCENARIOS, scenario_config
from delivery.server import serve
from delivery.simulation import Simulation, compare

ROWS = [("placed", "orders placed", "{}"), ("delivered", "delivered", "{}"),
        ("abandoned", "abandoned", "{}"), ("declined", "payment declined", "{}"),
        ("throughput", "dispatches per second", "{:.2f}"), ("dispatch_p50", "dispatch time p50", "{:.1f}s"),
        ("dispatch_p95", "dispatch time p95", "{:.1f}s"), ("peak_queue", "peak inbound queue", "{}"),
        ("revenue_lost", "revenue lost", "${:,.0f}")]


def print_table(columns):
    """columns: {heading: summary dict}"""
    print(f"  {'':24}" + "".join(f"{h:>18}" for h in columns))
    for key, label, fmt in ROWS:
        print(f"  {label:24}" + "".join(f"{fmt.format(s[key]):>18}" for s in columns.values()))


def main(argv=None):
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    p = argparse.ArgumentParser(prog="python main.py", description="Food delivery mediator simulator")
    sub = p.add_subparsers(dest="cmd")
    s = sub.add_parser("serve", help="open the web dashboard (default)")
    s.add_argument("--port", type=int, default=8770)
    s.add_argument("--no-browser", action="store_true")
    s.add_argument("-s", "--scenario", default="normal", choices=SCENARIOS)
    r = sub.add_parser("run", help="run one simulation and print a report")
    r.add_argument("-s", "--scenario", default="surge", choices=SCENARIOS)
    r.add_argument("-d", "--duration", type=float, default=300)
    r.add_argument("--seed", type=int, default=7)
    r.add_argument("--json", action="store_true", help="print the summary as JSON")
    c = sub.add_parser("compare", help="run scenarios side by side through the mediator")
    c.add_argument("-s", "--scenario", nargs="+", choices=SCENARIOS, help="scenarios to compare (default: all)")
    c.add_argument("--seed", type=int, default=7)
    sub.add_parser("scenarios", help="list scenarios")
    a = p.parse_args(argv)

    if a.cmd == "run":
        sim = Simulation(scenario_config(a.scenario, seed=a.seed, duration=a.duration)).run()
        summary = sim.summary()
        if a.json:
            print(json.dumps(summary, indent=2))
        else:
            print(f"\n{SCENARIOS[a.scenario][0]}, {a.duration:g}s\n")
            print_table({"mediator": summary})
            print(f"\n  Bottleneck: {sim.bottleneck()['text']}\n")
    elif a.cmd == "compare":
        res = compare(a.scenario, seed=a.seed)
        print("\nScenarios side by side (same seed)\n")
        print_table({k: v["summary"] for k, v in res.items()})
        print()
    elif a.cmd == "scenarios":
        for k, (name, text, _) in SCENARIOS.items():
            print(f"  {k:18} {name}: {text}")
    else:
        a = a if a.cmd == "serve" else p.parse_args(["serve"])
        serve(port=a.port, scenario=a.scenario, open_browser=not a.no_browser)


if __name__ == "__main__":
    main()
