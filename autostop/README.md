# Autostop Manager (POC)

Template-scoped report / notify / stop for Coder workspaces, runnable locally or as a
Kubernetes CronJob.

**Problem it addresses:** saving a template autostop requirement recalculates
`max_deadline` from each running build's completion time. Older builds get clamped
to `now + 2h` and stop off-schedule, outside quiet hours, without notifying owners.
This tool flags those workspaces (`off_schedule`), emails owners and the template
owner, and can stop idle workspaces.

## Flags per workspace

| Flag | Meaning |
|------|---------|
| `imminent_stop` | `min(deadline, max_deadline)` within `stop_window_hours` |
| `off_schedule` | imminent stop driven by `max_deadline` that is not on a required day, not minute-aligned (cron-derived values are `HH:MM:00.000000`; the now+2h clamp keeps the seconds of "now"), or not at the owner's quiet-hours start |
| `idle` | `last_used_at` older than `idle_threshold_hours` |

| `over_interval` | only with `ignore_required_stop_day`: running longer than `max_running_hours` |

Only running, non-prebuild workspaces of the exact template ID are considered.

## Interval-only mode (`ignore_required_stop_day`)

`ignore_required_stop_day: true` (CLI `--ignore-required-stop-day`) with
`max_running_hours: N` (CLI `--max-running-hours N`) makes the script ignore the
template's required stop day and the build's `deadline`/`max_deadline` entirely.
A workspace's stop time is `start build completed + N hours`; `action: stop` stops
**only** workspaces past that interval (idle is still reported, not acted on).

The script cannot change Coder's `max_deadline`. To make the interval the effective
policy, set the template's required stop days to none
(`coder templates edit <tpl> --autostop-requirement-weekdays none`), which also
avoids the now+2h clamp. The script logs a warning if the template still has a
required stop day.

```bash
./autostop_manager.py --template my-template --ignore-required-stop-day --max-running-hours 336 --action stop --dry-run
```

## Actions

| `action` | Report | Email owners / template owner | Stop idle |
|----------|--------|-------------------------------|-----------|
| `report_only` | yes | no | no |
| `report_idle` | yes | yes | no |
| `stop` | yes | yes | yes |

`dry_run: true` (default) never stops anything and prints emails instead of sending.
With `dry_run: false` and an empty `smtp.host`, emails are also printed.

For a first real-mail test, set `notify.redirect_to` to a single mailbox: every email
goes there (original recipients listed in the body) and `action: report_idle` never
stops anything. STARTTLS verifies the relay certificate by default; set
`smtp.tls_verify: false` only when the relay's certificate doesn't match `smtp.host`.

Emails are de-duplicated for a stateless CronJob: sent only on the run where a
workspace enters the stop window, becomes idle, or right after the template was
saved (`updated_at` within `run_interval_minutes`). Keep `run_interval_minutes`
equal to the CronJob schedule. `--notify-all` disables this for one-off runs.

## Stop only inside the owner's quiet hours (`stop_only_in_quiet_hours`)

With `action: stop`, `stop_only_in_quiet_hours: true` (CLI `--stop-only-in-quiet-hours`)
stops a qualifying workspace (idle, or over `max_running_hours` in interval-only mode)
**only while the workspace owner is inside their quiet hours**. Otherwise the stop is
deferred (action `deferred:quiet-hours <next start>`) and made by a later run that lands
inside the window.

- Quiet hours come from each owner's Coder schedule (`GET /api/v2/users/{id}/quiet-hours`),
  evaluated in the **owner's** timezone. Coder defines only the start time, so the window is
  `start .. start + quiet_hours_window_hours` (default 4h; CLI `--quiet-hours-window-hours`),
  including windows that cross midnight.
- Owners whose quiet hours cannot be read are deferred by default.
- Overrides (only meaningful with `stop_only_in_quiet_hours`):
  - `force: true` / `--force`: also stop workspaces whose owner's quiet hours are
    **unknown**. Owners known to be outside their quiet hours still wait.
  - `force_all: true` / `--force-all`: ignore quiet hours and stop **every**
    qualifying workspace now. The action reads `stopped (force-all: ...)` and the owner
    email says the stop was an administrator override.
  - Neither flag stops anything that doesn't already qualify (idle / over `max_running_hours`).
- Keep the CronJob interval (`run_interval_minutes`) shorter than the window; the script
  warns if it isn't.
- The owner is emailed once when the workspace first qualifies ("will be stopped during
  your quiet hours, from <time>") and again when it is stopped.

```bash
./autostop_manager.py --template my-template --ignore-required-stop-day --max-running-hours 336 \
  --action stop --stop-only-in-quiet-hours --quiet-hours-window-hours 4 --dry-run
# one-off override: stop everything that qualifies, regardless of quiet hours
./autostop_manager.py --template my-template --ignore-required-stop-day --max-running-hours 336 \
  --action stop --stop-only-in-quiet-hours --force-all --notify-all
```

Verified live: see [docs/quiet-hours-evidence-2026-11-13.md](docs/quiet-hours-evidence-2026-11-13.md).

## Local run

```bash
pip install -r requirements.txt
export CODER_URL=https://coder.example.com
export CODER_TOKEN=$(coder login token)
./autostop_manager.py --config config.example.yaml --template my-template --dry-run
./autostop_manager.py --config config.example.yaml --template my-template --dry-run --action report_idle --notify-all
./autostop_manager.py --config config.example.yaml --template my-template --output json
```

Exit codes: `0` ok, `1` config/API error, `2` partial failure (some stops/emails failed).

## Kubernetes

```bash
# 1. Secret (once)
kubectl -n coder create secret generic autostop-secrets \
  --from-literal=CODER_URL=https://coder.example.com \
  --from-literal=CODER_TOKEN=<template-admin token> \
  --from-literal=SMTP_USERNAME= --from-literal=SMTP_PASSWORD=

# 2a. ConfigMap mode: script + config packed from local files
./deploy.sh -n coder --config-file my-config.yaml

# 2b. git-pull mode: initContainer clones the repo each run
./deploy.sh -n coder --mode git --git-ref master --config-file my-config.yaml

# Options
./deploy.sh --schedule "*/15 * * * *"   # also set run_interval_minutes: 15
./deploy.sh --run-now                   # one-off Job from the CronJob
./deploy.sh --kubectl-dry-run           # render YAML only
./deploy.sh --kubeconfig ~/rke2.yaml
```

Changing config: edit the file and re-run `deploy.sh`; the next scheduled run picks it up.

The token needs rights to read template/user details (emails, quiet hours) and to
create stop builds for other users' workspaces. Verified: a **service account with
Organization Admin** in the template's organization is sufficient (no site roles), and
gives a distinct initiator in build history and the audit log
(`coder users create --service-account --username autostop-bot`,
`coder organizations members edit-roles autostop-bot organization-admin --org <org>`,
`coder tokens create --user autostop-bot --name autostop --lifetime <d>`).
See [docs/stop-evidence-2026-11-10.md](docs/stop-evidence-2026-11-10.md).

Image: `python:3.12-slim`; dependencies are `pip install`ed at job start (needs PyPI
egress). For air-gapped clusters, build an image with `requirements.txt` baked in.

## Tests

```bash
pip install pytest -r requirements.txt
python -m pytest -q tests
```
