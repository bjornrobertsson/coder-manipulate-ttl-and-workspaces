$ python example_usage.py
🚀 Coder Workspace Management Agents - Example Usage
================================================================================
============================================================
EXAMPLE 1: Basic Workspace Operations
============================================================
✅ Connected to Coder API successfully
📊 Total workspaces: 66
🟢 Running workspaces: 1

Running workspaces:
  - $USER/$WORKSPACE ($TEMPLATE) - running

============================================================
EXAMPLE 2: Quiet Hours Status Check
============================================================
🕐 Current time: 2025-10-06 14:07:45 UTC
🌙 Quiet hours active: No
⏰ Grace period over: No
🛑 Workspaces to stop: 0

📋 Generating detailed report...
Action required: No action required - outside quiet hours

============================================================
EXAMPLE 3: TTL Compliance Report
============================================================
📊 Total workspaces analyzed: 66
🔴 Expired: 0
🟡 Expiring soon: 1
🟢 Running normally: 0
⚫ Stopped: 65

🟡 Workspaces EXPIRING SOON:
  - $USER/$WORKSPACE: 53m

============================================================
EXAMPLE 4: Comprehensive Workspace Analysis
============================================================
🔍 Performing combined workspace analysis...
📊 Analysis Results:
  Total running workspaces: 1
  Affected by quiet hours: 0
  TTL expired: 0
  TTL expiring soon: 1

✅ No immediate actions needed

============================================================
EXAMPLE 5: Dry-Run Workspace Management
============================================================
🧪 Running in DRY-RUN mode (no actual changes will be made)

🌙 Simulating quiet hours workspace stopping...

================================================================================
WORKSPACE CATEGORIZATION
================================================================================

🌅 RUNNING PAST QUIET HOURS END (1)
------------------------------------------------------------
  • $USER/$WORKSPACE ($TEMPLATE) - running
    TTL: 53m

================================================================================

⏰ Grace period not over yet, no workspaces will be stopped
💡 Use --force to stop TTL-expired workspaces regardless of quiet hours
ℹ️  No workspaces would be affected by quiet hours policy

================================================================================
EXAMPLE EXECUTION SUMMARY
================================================================================
✅ PASSED: Basic Workspace Operations
✅ PASSED: Quiet Hours Status Check
✅ PASSED: TTL Compliance Monitoring
✅ PASSED: Combined Analysis
✅ PASSED: Dry-Run Operations

📊 Overall: 5/5 examples completed successfully

---

$ python prune_workspaces.py --cleanup --dry-run

🌙 WORKSPACES WITHIN QUIET HOURS PERIODS (52)
================================================================================

👤 $USER
   Quiet Hours: 13:32 (Europe/London)
   Current Period: 13:32 - 21:32
------------------------------------------------------------
Workspace                 Template                       Status    Created
------------------------  -----------------------------  --------  ----------
AgentID                   kubernetes-agent-id            running   2025-04-09
apricot-newt-96           template-example               stopped   2025-09-11
...
WithSystemD               VSCode-Jupyter-GPU-systemd     stopped   2025-07-09


🧪 [DRY RUN] Cleaning up 1 running workspaces:
------------------------------------------------------------
  🧪 [DRY RUN] Would stop: $USER/$WORKSPACE ($TEMPLATE) - running
     Owner: bjorn
     Reason: Pruned during quiet hours

📊 Cleanup completed: 1/1 workspaces processed successfully


---

$ python prune_workspaces.py --cleanup

🌙 WORKSPACES WITHIN QUIET HOURS PERIODS (52)
================================================================================

👤 $USER
   Quiet Hours: 13:32 (Europe/London)
   Current Period: 13:32 - 21:32
------------------------------------------------------------
Workspace                 Template                       Status    Created
------------------------  -----------------------------  --------  ----------
AgentID                   kubernetes-agent-id            running   2025-04-09
apricot-newt-96           template-example               stopped   2025-09-11
...
WithSystemD               VSCode-Jupyter-GPU-systemd     stopped   2025-07-09


🛑 Cleaning up 1 running workspaces:
------------------------------------------------------------
  🛑 Stopping: $USER/$WORKSPACE ($TEMPLATE) - running
     Owner: $USER
     Reason: Pruned during quiet hours
Successfully initiated stop for workspace 284d08ed-31ce-4b93-b482-9de727f7f731: Pruned during quiet hours
     Result: ✅ Success

📊 Cleanup completed: 1/1 workspaces processed successfully