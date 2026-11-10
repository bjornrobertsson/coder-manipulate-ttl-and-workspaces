# Evidence: autostop_manager.py stops a workspace (2026-11-10)

This test shows that the script itself stops a workspace. All evidence comes
from Coder's own records (build history and audit log), not from the script's
output.

## Setup (Coder v2.38.5 test deployment; RKE2 cluster)

| Item | Value | Why |
|------|-------|-----|
| Template | `autostop-poc-stoptest`, agent-only, `autostop_requirement.days_of_week = []`, default TTL 8h | Coder's own autostop is not due for 8h, so Coder cannot be what stops it |
| Script identity | service account `autostop-bot`, **Organization Admin** in `coder`, no site roles | A dedicated identity that only the script uses |
| Workspaces | `poc-old` (started 15:32:28) and `poc-new` (started 15:36:13; the control) | Same owner and same template |
| Script run | in-cluster Job (ConfigMap mode), `action: stop`, `dry_run: false`, `ignore_required_stop_day: true`, `max_running_hours: 0.0518` (3.1 min), `idle_threshold_hours: 24` | The interval falls between the two workspaces' ages, and idle cannot trigger a stop |

## Before (15:36:13Z)

```
poc-old  build#1 start/running reason=initiator initiator=admin started=15:32:28.48 deadline=23:32:28 max_deadline=None
poc-new  build#1 start/running reason=initiator initiator=admin started=15:36:13.31 deadline=23:36:13 max_deadline=None
```

## Job pod

```
container: 2026-11-10T15:36:40Z -> 2026-11-10T15:36:47Z exit=0
| poc-old | running | ... | over_interval | stopped notify-logged |
| poc-new | running | ... | imminent_stop | notify-logged         |
```

## After: Coder build history (15:37:11Z)

```
poc-old  build#1 start running  reason=initiator initiator=admin         created=15:32:26.90 completed=15:32:28.48
poc-old  build#2 stop  stopped  reason=initiator initiator=autostop-bot  created=15:36:47.30 completed=15:36:52.14
poc-new  build#1 start running  reason=initiator initiator=admin         created=15:36:08.18 completed=15:36:13.31
```

## After: Coder audit log (`q=username:autostop-bot`)

```
2026-11-10T15:36:52.31Z autostop-bot stop workspace_build status=200 "{user} stopped workspace {target}" build_reason=initiator workspace=poc-old
```

## Conclusion

- `poc-old` got a **stop build initiated by `autostop-bot`**, the script's own identity.
- The build reason is `initiator`, meaning an API call. Coder's scheduler would have recorded `autostop`.
- The stop build was created at 15:36:47.30, during the Job container's run (15:36:40 to 15:36:47).
- Coder's own stop time for `poc-old` was 23:32 and there was no `max_deadline`, so nothing else was due to stop it.
- The control `poc-new` (under the interval, same template and owner) was **not** stopped.
- **Organization Admin** in the workspace's organization is enough to stop other users' workspaces. Site Owner is not needed.

All test resources (user, service account, token, template, workspaces, namespace) were deleted after the run.
