# Autostop Manager POC - TODO

## Problem Statement

Saving an autostop requirement on a template recalculates `max_deadline` for every
running build, anchored to the build's completion time (not "now"). For builds older
than the most recent required-stop day, the result is in the past and gets clamped to
`now + 2h` (`enterprise/coderd/schedule/template.go`, `updateWorkspaceBuilds`).
Net effect: running workspaces stop ~2h after the save, off-schedule, outside quiet
hours, with no owner notification (tracked internally as CORE-802).

The "every N weeks" cadence is anchored to a global epoch (Monday 2 Jan 2023,
`TemplateAutostopRequirementEpoch`), not to the last stop, so "every 2 weeks" can
legitimately fall one week after a previous stop.

This POC gives template admins visibility (report), owner notification (email), and
optional controlled stopping for a single template, runnable locally or as a k8s
CronJob.

---

## Deliverables

### 1. Python script: `autostop/autostop_manager.py`

- [ ] Load config from YAML (`CONFIG_PATH`, default `/config/config.yaml`), with
      CLI overrides (`--template`, `--dry-run`, `--action`, `--config`)
- [ ] Config values:
  - [ ] `template` - template name (or ID) to scope to (required)
  - [ ] `organization` - optional, disambiguates template names across orgs
  - [ ] `dry_run` - default `true`; no stops, emails printed instead of sent
  - [ ] `action` - `report_only` | `report_idle` | `stop`
  - [ ] `notify.template_owner` - email the template owner/admin a summary
  - [ ] `notify.workspace_owner` - email each affected workspace owner
  - [ ] `idle_threshold_hours` - `last_used_at` older than this = idle
  - [ ] `stop_window_hours` - flag workspaces whose `deadline`/`max_deadline` is within this window
  - [ ] `smtp` - host, port, from_address, starttls (credentials from Secret)
- [ ] Coder API calls (reuse helpers from `coder-audit-simple/coder_audit.py`):
  - [ ] `GET /api/v2/templates` -> resolve template, `created_by_id`, `autostop_requirement`
  - [ ] `GET /api/v2/workspaces?q=template:<name>` -> running workspaces
  - [ ] `GET /api/v2/users/{id}` -> owner + template-creator email, `last_seen_at`
  - [ ] `GET /api/v2/users/{id}/quiet-hours` -> owner quiet-hours schedule/timezone
  - [ ] `POST /api/v2/workspaces/{id}/builds` `{"transition":"stop"}` -> stop (only when `action=stop` and `dry_run=false`)
- [ ] Classification per workspace:
  - [ ] `imminent_stop` - `max_deadline`/`deadline` within `stop_window_hours`
  - [ ] `off_schedule` - imminent stop not on the template's required day / outside owner quiet hours (the CORE-802 symptom)
  - [ ] `idle` - `last_used_at` older than `idle_threshold_hours`
  - [ ] Skip prebuilds and non-running builds
- [ ] Actions:
  - [ ] `report_only` - table/JSON to stdout (pod logs), no email
  - [ ] `report_idle` - report + email owners about idle / imminent-stop workspaces
  - [ ] `stop` - report + email + stop idle workspaces (respects `dry_run`)
- [ ] Email content:
  - [ ] Workspace owner: workspace name, template, expected stop time (owner TZ), reason, link
  - [ ] Template owner: one summary of all affected workspaces and actions taken
- [ ] Exit codes: `0` ok, `1` API/config error, `2` partial failure (some stops/emails failed)
- [ ] Unit tests for classification and deadline parsing (no live API)

### 2. Kubernetes manifests: `autostop/k8s/`

- [ ] `configmap.yaml` - `config.yaml` for the script (template, dry_run, action, ...)
- [ ] `secret.example.yaml` - `CODER_URL`, `CODER_TOKEN`, `SMTP_USERNAME`, `SMTP_PASSWORD` (example only, never commit real values)
- [ ] `cronjob.yaml` - schedule (default `*/30 * * * *`), `concurrencyPolicy: Forbid`, `python:3.12-slim`
- [ ] Script delivery, two modes:
  - [ ] **ConfigMap mode** - script + config packed into ConfigMaps from local files, mounted at `/app` and `/config`
  - [ ] **git-pull mode** - initContainer (`alpine/git`) clones this repo (`GIT_REPO`, `GIT_REF`) into an `emptyDir`; config still from ConfigMap
- [ ] Default namespace: `coder`; all manifests namespace-overridable
- [ ] Optional `Job` for one-off runs (e.g. immediately after saving a template change)

### 3. Deploy script: `autostop/deploy.sh`

- [ ] Flags:
  - [ ] `-n|--namespace` (default `coder`)
  - [ ] `--mode configmap|git` (default `configmap`)
  - [ ] `--config-file` -> `kubectl create configmap autostop-config --from-file=config.yaml=<file> --dry-run=client -o yaml | kubectl apply -f -`
  - [ ] `--script-file` (configmap mode) -> `autostop-script` ConfigMap from `autostop_manager.py`
  - [ ] `--git-repo` / `--git-ref` (git mode)
  - [ ] `--schedule` (cron expression override)
  - [ ] `--run-now` (create a one-off Job from the CronJob)
  - [ ] `--kubectl-dry-run` (render only, apply nothing)
  - [ ] `--kubeconfig` passthrough
- [ ] Create namespace if missing; warn if the Secret is missing rather than creating it with placeholders

### 4. Docs

- [ ] `autostop/README.md` - local run, k8s deploy (both modes), config reference, sample output
- [ ] Update root `README.md` / `PROJECT_STRUCTURE.md` with the new `autostop/` directory

---

## Reuse

| Source | Reuse |
|--------|-------|
| `coder-audit-simple/coder_audit.py` | `get_token()`, `get_fqdn()`, `get_workspaces()`, `get_templates()`, `format_ttl()`, `format_time_remaining()` |
| `agents/workspace_controller.py` | Workspace stop build call |
| `agents/ttl_monitor_agent.py` | Deadline / TTL prediction, user/org filtering |
| `agents/quiet_hours_agent.py`, `agents/enterprise_quiet_hours.py` | Owner quiet-hours lookup |

---

## Target layout

```
autostop/
├── TODO.md
├── README.md
├── autostop_manager.py
├── requirements.txt          # requests, pyyaml, tabulate
├── config.example.yaml
├── deploy.sh
├── tests/
│   └── test_classification.py
└── k8s/
    ├── configmap.yaml
    ├── secret.example.yaml
    ├── cronjob.yaml          # configmap mode
    └── cronjob-git.yaml      # git-pull mode
```

---

## Config example (`config.example.yaml`)

```yaml
template: "my-template"
organization: ""            # optional
dry_run: true
action: "report_only"       # report_only | report_idle | stop
idle_threshold_hours: 24
stop_window_hours: 4
notify:
  template_owner: true
  workspace_owner: true
smtp:
  host: "smtp.example.com"
  port: 587
  starttls: true
  from_address: "coder-autostop@example.com"
```

## Environment variables

| Variable | Source | Notes |
|----------|--------|-------|
| `CODER_URL` | Secret | Coder deployment URL |
| `CODER_TOKEN` | Secret | Token with template-admin/owner scope (needs user emails) |
| `SMTP_USERNAME` / `SMTP_PASSWORD` | Secret | Optional |
| `CONFIG_PATH` | CronJob env | Default `/config/config.yaml` |

---

## Validation plan

1. Local: `--dry-run --action report_only` against a test template
2. Change the template autostop requirement on a test deployment; confirm the script flags the `now + 2h` builds as `off_schedule`
3. `action=report_idle`, `dry_run=true` -> emails rendered to logs
4. Deploy CronJob in `coder` namespace (configmap mode), then git mode
5. `action=stop`, `dry_run=false` on a disposable workspace only
