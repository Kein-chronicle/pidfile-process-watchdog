---
name: service-health-watchdog
description: Design and implement a self-healing watchdog for a long-running local service (bot, daemon, poller) without false restarts, restart storms, or racing killers. Use when a service dies silently, when a stale pid file makes a dead service look healthy, when a watchdog kills the wrong process or restarts a service that is still booting, when two supervisors fight, or when you need restart-with-backoff and give-up logic.
---

# service-health-watchdog

Lessons from long-running bot and daemon stacks that died silently. The code (`scripts/watchdog.py`) is a small pure
state machine plus a pid/cwd probe; it is tested without touching real processes.

## Health = "a valid poller exists", nothing else

A healthy service needs **all three**:
1. pid file contains an integer,
2. that pid is alive,
3. **that pid's working directory is the service's root.**

(3) is the one people skip. Servers usually delete the pid file only on clean exit, so after a crash or reboot a
stale pid file may point at an unrelated process forever and the check stays green. Do **not** decide health from
the supervisor's job state (launchd says "running") - kickstarting under a manually started instance gives two
instances of a single-consumer service (for example two pollers on one API token, which the API answers with conflict errors).

## Decision rules (in `Watchdog.tick`)

| Probe | Action |
|---|---|
| HEALTHY | reset failure counter |
| UNKNOWN (lsof failed, can't tell) | **do nothing.** A false restart creates the outage it was meant to prevent |
| DEAD within `grace` seconds after a restart | wait (boot race, wake from sleep) |
| DEAD | restart; count a failure |
| `give_up_after` consecutive restarts with no recovery | GIVEUP + notify a human; stop restarting |
| >= `flap_per_hour` restarts in an hour | FLAPPING warning (still restarts) |

Count *consecutive failures without recovery*, not restarts per hour: a per-hour count gives up on a service that
dies and recovers every 5 minutes, which is exactly the one worth keeping alive.

## Other rules worth following

- **One killer.** If two components may kill/restart the same service, a stale pid + a booting server will
  kill each other. Retire the old watchdog; don't run both.
- **Log transitions, not ticks.** A line per minute buries the one incident.
- **Process matching:** `pgrep -f` on macOS excludes ancestors by default and can silently miss a live process.
  Scan `ps -axo pid,ppid,command` instead. Also: a loose pattern like `node.*server\.js` will match an
  unrelated project's `server.js` - verify by cwd before `kill -9`.
- **Silent no-op is the worst failure.** A service started with a missing plugin or configuration can boot without any error and simply never connect.
  Add a **preflight** to the launcher (exit non-zero instead of starting a dead service) and a post-boot check that the pid file appears.
  The same applies to this watchdog: on UNKNOWN it prints one line to stderr so a watchdog that can never act is not invisible.
- **Shared runtime first.** If several independent services die at once, suspect the shared runtime
  (a deleted interpreter, a dead shim, a changed PATH) before debugging each one. Find the error in the
  *service's own* log (MCP/stderr), not in the supervisor's terminal-escape-filled log.
- **Disable the watchdog while you repair.** Otherwise it kickstart-loops the half-booted service every 2 minutes
  and you can't see the original cause.
- Verification: `kill -9` the service three times; each must auto-recover within ~70 s. Test the GIVEUP path in
  isolation.

## Use

```bash
python3 scripts/watchdog.py --pid-file /path/service.pid --root /path/service \
        --restart-cmd "launchctl kickstart -k gui/\$(id -u)/com.example.svc" --state /tmp/wd.json \
        [--grace 90] [--give-up-after 5] [--flap-per-hour 3] [--dry-run]
python3 tests/test_watchdog.py
```
Run it from a 60-second scheduler. `--dry-run` prints the decision without restarting. Exit `3` means the restart command was run and failed. On Linux the working directory comes from `/proc`; elsewhere `lsof` is used.

Unreadable or malformed saved state is unmeasured (exit 3): no restart and no overwrite. Dry-run never changes state. State writes replace the file atomically. Run only one watchdog process per state file; this reference does not serialize competing instances. Restart commands are trusted shell configuration, never untrusted input.
