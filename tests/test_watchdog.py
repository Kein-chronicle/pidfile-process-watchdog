import os, sys, tempfile
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))
from watchdog import Watchdog, probe_pid, HEALTHY, DEAD, UNKNOWN

ok = True
def expect(name, got, want):
    global ok; g = got == want; ok &= g; print(("ok   " if g else "FAIL ") + f"{name}: {got!r} (want {want!r})")

w = Watchdog(grace=90, give_up_after=5)
expect("unknown -> no action", w.tick(UNKNOWN, 1000), "none")
expect("dead -> restart", w.tick(DEAD, 1000), "restart")
expect("dead inside grace -> wait", w.tick(DEAD, 1030), "wait")
expect("recovery resets counter", (w.tick(HEALTHY, 1100), w.consecutive), ("none", 0))

w = Watchdog(grace=10, give_up_after=5, flap_per_hour=99); t = 0; acts = []
for _ in range(7):
    t += 20; acts.append(w.tick(DEAD, t))
expect("5 restarts then giveup, then silent", acts, ["restart"]*5 + ["giveup", "none"])

# dies and recovers every 5 min must never give up (per-hour counting would)
w = Watchdog(grace=10, give_up_after=5, flap_per_hour=99); t = 0; acts = set()
for _ in range(20):
    t += 300; acts.add(w.tick(DEAD, t)); w.tick(HEALTHY, t + 60)
expect("flapping-but-recovering never gives up", "giveup" in acts, False)

w = Watchdog(grace=1, give_up_after=99, flap_per_hour=3); t = 0; last = None
for _ in range(3):
    t += 100; last = w.tick(DEAD, t)
expect("3 restarts/hour warns", last, "restart+flapping")

d = tempfile.mkdtemp(); pf = os.path.join(d, "s.pid")
expect("missing pid file -> DEAD", probe_pid(pf, d), DEAD)
open(pf, "w").write("not-a-number"); expect("garbage pid file -> DEAD", probe_pid(pf, d), DEAD)
open(pf, "w").write("999999"); expect("dead pid -> DEAD", probe_pid(pf, d), DEAD)
open(pf, "w").write(str(os.getpid()))
expect("alive pid, wrong cwd (stale-pid case) -> DEAD", probe_pid(pf, d), DEAD)
os.chdir(d)
expect("alive pid, right cwd -> HEALTHY", probe_pid(pf, d), HEALTHY)


# CLI: a failing restart command is reported (exit 3), --dry-run never runs it
import subprocess, json
st = os.path.join(tempfile.mkdtemp(), "wd.json"); me = os.path.dirname(os.path.abspath(__file__))
cli = [sys.executable, os.path.join(me, "..", "scripts", "watchdog.py"), "--pid-file", "/nonexistent.pid", "--root", me, "--state", st]
r = subprocess.run(cli + ["--restart-cmd", "exit 7"], capture_output=True, text=True)
expect("failing restart command propagates as exit 3", r.returncode, 3)
st2 = os.path.join(tempfile.mkdtemp(), "wd.json"); marker = os.path.join(tempfile.mkdtemp(), "ran")
r = subprocess.run(cli[:-1] + [st2, "--restart-cmd", f"touch {marker}", "--dry-run"], capture_output=True, text=True)
expect("--dry-run does not run the restart command", (r.returncode, os.path.exists(marker)), (0, False))
ok &= subprocess.run([sys.executable, os.path.join(os.path.dirname(os.path.abspath(__file__)), "test_release_regressions.py")]).returncode == 0
sys.exit(0 if ok else 1)
