# Evidence: stop only inside the owner's quiet hours (2026-11-13)

This test shows that `stop_only_in_quiet_hours` stops a workspace only while its
owner is inside their Coder quiet hours, and that `force` and `force_all` behave as
documented. All evidence comes from Coder's build history and audit log.

## Setup (Coder v2.38.5 test deployment; RKE2 cluster)

| Item | Value |
|------|-------|
| Template | `autostop-qh-test`, agent-only, no required stop days, default TTL 8h (Coder not due to stop anything) |
| Script identity | service account `autostop-bot`, Organization Admin only |
| Owner `qh-inside` | quiet hours `CRON_TZ=Asia/Tokyo 0 23 * * *`. At the run it was 23:16 in Tokyo, **inside** the 4h window |
| Owner `qh-outside` | quiet hours `CRON_TZ=America/Chicago 0 14 * * *`. At the run it was 08:16 in Chicago, **outside** the window |
| Workspaces | `qh-inside/ws-in`, `qh-outside/ws-out`; same template, both started at about 14:14:45 UTC |
| Config | `action: stop`, `dry_run: false`, `ignore_required_stop_day: true`, `max_running_hours: 0.02` (both workspaces qualify), `stop_only_in_quiet_hours: true`, `quiet_hours_window_hours: 4` |
| Runs | in-cluster Jobs (ConfigMap mode) |

## Run 1: `stop_only_in_quiet_hours` (Job container 14:16:24 to 14:16:29 UTC, exit 0)

```
| qh-inside  | ws-in  | over_interval | stopped notify-logged                                       |
| qh-outside | ws-out | over_interval | deferred:quiet-hours Fri 2026-11-13 14:00 CST notify-logged |
```

The owner of `ws-out` was told: *"... will be stopped during your quiet hours, from Fri 2026-11-13 14:00 CST."*

Coder build history afterwards:

```
qh-inside/ws-in    build#1 start running  reason=initiator initiator=admin         created=14:14:43.11
qh-inside/ws-in    build#2 stop  stopped  reason=initiator initiator=autostop-bot  created=14:16:29.19
qh-outside/ws-out  build#1 start running  reason=initiator initiator=admin         created=14:14:45.82
```

## Run 2: `force: true` (14:17:44 to 14:17:48, exit 0)

`ws-out`'s owner has **known** quiet hours and is outside them, so `force` does not apply:

```
| qh-outside | ws-out | over_interval | deferred:quiet-hours Fri 2026-11-13 14:00 CST notify-logged |
qh-outside/ws-out  build#1 start running  (no new build)
```

## Run 3: `force_all: true` (14:17:58 to 14:18:03, exit 0)

```
| qh-outside | ws-out | over_interval | stopped (force-all: outside quiet hours) notify-logged |
qh-outside/ws-out  build#2 stop  stopped  reason=initiator initiator=autostop-bot  created=14:18:02.94
```

## Coder audit log (`q=username:autostop-bot`, workspace builds)

```
2026-11-13T14:16:30.33Z autostop-bot stop status=200 ws-in
2026-11-13T14:18:04.33Z autostop-bot stop status=200 ws-out
```

## Conclusion

- With `stop_only_in_quiet_hours`, only the workspace whose owner was inside their quiet
  hours (evaluated in the owner's own timezone) was stopped. The other was deferred, and
  its owner was told when the stop would happen.
- `force` did not override known quiet hours.
- `force_all` stopped the deferred workspace outside quiet hours, and the action records
  it as a forced stop.
- `force` with unknown quiet hours is covered by unit tests (`tests/`). This test could
  not make a real owner's quiet hours unreadable.

All test resources were deleted after the run.
