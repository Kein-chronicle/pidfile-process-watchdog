"""Replay a day of probes through the decision machine. No process is touched."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))
from watchdog import Watchdog, HEALTHY, DEAD, UNKNOWN

w = Watchdog(grace=90, give_up_after=3, flap_per_hour=99)
timeline = [("healthy", HEALTHY, 0), ("cannot inspect", UNKNOWN, 60), ("dies", DEAD, 120), ("still dead, in grace", DEAD, 150),
            ("still dead, grace over", DEAD, 260), ("still dead", DEAD, 400), ("still dead", DEAD, 540), ("recovers", HEALTHY, 700)]
for label, probe, t in timeline:
    print(f"t={t:<4} {label:<24} -> {w.tick(probe, t)}")
