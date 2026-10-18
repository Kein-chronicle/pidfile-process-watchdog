#!/usr/bin/env python3
"""service-health-watchdog: probe + pure decision state machine."""
import argparse, json, math, os, subprocess, sys, tempfile, time

HEALTHY, DEAD, UNKNOWN = "HEALTHY", "DEAD", "UNKNOWN"


class Watchdog:
    def __init__(self, grace=90, give_up_after=5, flap_per_hour=3, state=None):
        self.grace, self.give_up_after, self.flap_per_hour = grace, give_up_after, flap_per_hour
        s = state or {}
        self.consecutive = s.get("consecutive", 0)
        self.last_restart = s.get("last_restart", 0.0)
        self.restarts = s.get("restarts", [])
        self.gave_up = s.get("gave_up", False)

    def tick(self, probe, now):
        """returns one of: none | wait | restart | giveup | restart+flapping"""
        if probe == HEALTHY:
            self.consecutive, self.gave_up = 0, False
            return "none"
        if probe == UNKNOWN:
            return "none"                           # cannot tell: acting on a guess causes outages
        if self.gave_up:
            return "none"
        if now - self.last_restart < self.grace:
            return "wait"                           # still booting / just woke from sleep
        if self.consecutive >= self.give_up_after:
            self.gave_up = True
            return "giveup"
        self.consecutive += 1
        self.last_restart = now
        self.restarts = [t for t in self.restarts if now - t < 3600] + [now]
        return "restart+flapping" if len(self.restarts) >= self.flap_per_hour else "restart"

    def state(self):
        return {"consecutive": self.consecutive, "last_restart": self.last_restart,
                "restarts": self.restarts, "gave_up": self.gave_up}


def probe_pid(pid_file, root):
    """HEALTHY only if pid file int + alive + cwd == root. UNKNOWN if we cannot inspect."""
    try:
        raw = open(pid_file).read().strip()
    except FileNotFoundError:
        return DEAD
    except OSError:
        return UNKNOWN
    if not raw.isdigit():
        return DEAD
    if len(raw) > 10 or not 1 <= int(raw) <= 2147483647: return UNKNOWN
    pid = int(raw)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return DEAD
    except PermissionError:
        pass
    proc_cwd = f"/proc/{pid}/cwd"                      # Linux: no lsof needed
    if os.path.islink(proc_cwd):
        try: return HEALTHY if os.path.realpath(os.readlink(proc_cwd)) == os.path.realpath(root) else DEAD
        except OSError: return UNKNOWN
    try:
        out = subprocess.run(["lsof", "-a", "-p", str(pid), "-d", "cwd", "-Fn"],
                             capture_output=True, text=True, timeout=10)
    except Exception:
        return UNKNOWN
    if out.returncode != 0 or not out.stdout:
        return UNKNOWN                              # empty output is not "wrong cwd"
    cwd = next((l[1:] for l in out.stdout.splitlines() if l.startswith("n")), None)
    if cwd is None:
        return UNKNOWN
    return HEALTHY if os.path.realpath(cwd) == os.path.realpath(root) else DEAD   # stale pid, other process


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pid-file", required=True); ap.add_argument("--root", required=True)
    ap.add_argument("--restart-cmd", required=True); ap.add_argument("--state", required=True)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--grace", type=int, default=90, help="seconds to wait after a restart before judging again")
    ap.add_argument("--give-up-after", type=int, default=5, help="consecutive restarts without recovery before giving up")
    ap.add_argument("--flap-per-hour", type=int, default=3, help="restarts per hour that trigger a flapping warning")
    a = ap.parse_args()
    try:
        st = json.load(open(a.state))
    except FileNotFoundError:
        st = None
    except (OSError, ValueError):
        print("UNMEASURED: state is unreadable; refusing restart or overwrite", file=sys.stderr); return 3
    if st is not None and (not isinstance(st, dict) or type(st.get("consecutive")) is not int or st["consecutive"] < 0
        or type(st.get("gave_up")) is not bool or not isinstance(st.get("restarts"), list)
        or not all(type(t) in (int, float) and math.isfinite(t) for t in st["restarts"])
        or type(st.get("last_restart")) not in (int, float) or not math.isfinite(st["last_restart"])):
        print("UNMEASURED: invalid state; refusing restart or overwrite", file=sys.stderr); return 3
    if a.grace < 0 or a.give_up_after < 1 or a.flap_per_hour < 1:
        print("invalid policy limits", file=sys.stderr); return 2
    wd = Watchdog(grace=a.grace, give_up_after=a.give_up_after, flap_per_hour=a.flap_per_hour, state=st)
    now = time.time(); probe = probe_pid(a.pid_file, a.root)
    action = wd.tick(probe, now)
    if probe == UNKNOWN:
        print(f"{time.strftime('%F %T')} probe=UNKNOWN: cannot inspect the process (is lsof installed?); taking no action", file=sys.stderr)
    if action != "none":
        print(f"{time.strftime('%F %T')} probe={probe} action={action}")      # transitions only
    rc = 0
    if action.startswith("restart") and not a.dry_run:
        rc = subprocess.run(a.restart_cmd, shell=True).returncode       # the restart command runs through a shell: never build it from untrusted input
        if rc: print(f"restart command exited {rc}", file=sys.stderr)
    if action == "giveup":
        print("GIVEUP: restarts did not recover the service - notify a human")
    if not a.dry_run:
        parent = os.path.dirname(os.path.abspath(a.state))
        fd, temporary = tempfile.mkstemp(prefix=".watchdog-", dir=parent)
        try:
            with os.fdopen(fd, "w") as state_file:
                json.dump(wd.state(), state_file); state_file.flush(); os.fsync(state_file.fileno())
            os.replace(temporary, a.state)
        finally:
            if os.path.exists(temporary): os.unlink(temporary)
    return 3 if rc else 0           # 3: the restart was attempted and failed


if __name__ == "__main__":
    sys.exit(main())
