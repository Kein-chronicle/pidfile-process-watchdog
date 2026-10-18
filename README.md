# pidfile-process-watchdog

**A small process watchdog with an honest state machine: pid and working-directory identity, restart grace, flap warnings, and giving up.**

[![test](https://github.com/Kein-chronicle/pidfile-process-watchdog/actions/workflows/test.yml/badge.svg)](https://github.com/Kein-chronicle/pidfile-process-watchdog/actions/workflows/test.yml) ![license](https://img.shields.io/badge/license-MIT-blue.svg) ![dependencies](https://img.shields.io/badge/dependencies-none-brightgreen.svg)

## Why

Restarting on a guess causes outages. This watchdog counts a process healthy only if its pid file is alive and its working directory is the service root, does nothing when it cannot inspect, waits out a grace period, and stops after repeated failures instead of looping forever.

## Install

**As a Claude Code skill** (Claude uses it when the task matches the skill description):

```sh
git clone https://github.com/Kein-chronicle/pidfile-process-watchdog.git ~/.claude/skills/service-health-watchdog
```

For a single project, clone into `<project>/.claude/skills/service-health-watchdog` instead, then start a new Claude Code session.

**As plain scripts:**

```sh
git clone https://github.com/Kein-chronicle/pidfile-process-watchdog.git
cd pidfile-process-watchdog
```

**Requires:** Python 3.10+.

## Quick start

Replay a sequence of probes:

```console
$ python3 examples/quickstart.py
t=0    healthy                  -> none
t=60   cannot inspect           -> none
t=120  dies                     -> restart
t=150  still dead, in grace     -> wait
t=260  still dead, grace over   -> restart
t=400  still dead               -> restart
t=540  still dead               -> giveup
t=700  recovers                 -> none
```

The output above is real: it is produced by the files in `examples/`.

## Use it on your own files

```sh
python3 scripts/watchdog.py --pid-file /path/service.pid --root /path/service \
  --restart-cmd "launchctl kickstart -k gui/$(id -u)/com.example.svc" --state /tmp/wd.json --dry-run
```

Sample inputs for every file format are in `examples/` and `tests/`; the details are in [SKILL.md](SKILL.md).

## What it checks

- Probe: `HEALTHY` / `DEAD` / `UNKNOWN` (cannot inspect means no action).
- Decision machine: `none`, `wait`, `restart`, `restart+flapping`, `giveup`.
- State is a JSON file; run it from a 60-second scheduler. `--dry-run` prints the decision without restarting.
- `--grace`, `--give-up-after` and `--flap-per-hour` tune the state machine; exit `3` means the restart command failed; UNKNOWN prints a line to stderr.

## Limits

- Pid-file based; services without a pid file need a different probe.
- The working-directory check uses `/proc` on Linux and `lsof` elsewhere.
- `--restart-cmd` is run through a shell: build it yourself, never from untrusted input.

## Related projects

These solve neighbouring problems; use them when they fit better.

- **monit, supervisord, systemd `Restart=`, launchd `KeepAlive`**: full supervisors; this is a drop-in check for an existing scheduler

## More from the same collection

Small, tested tools that grew out of running AI agents and game/app pipelines for months:

- [**claude-code-memory-lint**](https://github.com/Kein-chronicle/claude-code-memory-lint): Lint a Claude Code memory folder: orphan files, missing files, oversized index lines, and the index lines that are silently cut at load.
- [**claude-code-session-cost**](https://github.com/Kein-chronicle/claude-code-session-cost): Estimate what a Claude Code project cost from its session logs, sub-agents included, with both cache-TTL price assumptions shown.
- [**claude-code-launchd-loops**](https://github.com/Kein-chronicle/claude-code-launchd-loops): Generate a macOS launchd job that runs Claude Code headless on a schedule, from one command.

## Development

```sh
python3 tests/test_release_regressions.py
```

The tests include inputs that are supposed to be rejected, so a green run also shows the checks can fail. See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

MIT. See [LICENSE](LICENSE).

If this saved you a debugging session, a star helps other people find it. Bug reports and failing test cases are even better.

<sub>Keywords: watchdog, process-supervision, devops, macos, linux, launchd, reliability, claude-code</sub>
