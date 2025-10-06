# Prune Workspaces Agent Documentation

## 🎯 **Overview**

The Prune Workspaces Agent identifies and manages workspaces that are within their owner's quiet hours periods. Unlike the general quiet hours agent that uses a global schedule, this agent respects individual user quiet hours configurations from the Coder enterprise API.

## 🌙 **Quiet Hours Definition**

**Quiet Hours Period**: From the user's configured quiet hours start time until **start time + duration hours**

- **Default Duration**: 8 hours baseline (configurable via `--duration` parameter)
- **User-Specific**: Each user's quiet hours are determined by their individual enterprise schedule
- **Timezone Aware**: Respects each user's configured timezone
- **Activity Aware**: Actual stopping may be delayed based on workspace activity detection
- **Flexible Enforcement**: Baseline duration may be extended if workspace shows ongoing activity

### Example:
- User's quiet hours start: `18:00 UTC` (6 PM)
- Duration: `8 hours baseline` (default)
- **Quiet hours period**: `18:00 - 02:00 next day UTC`
- **Actual behavior**: Workspace eligible for stopping at 02:00, but may be extended if showing activity

## 🚀 **Usage Examples**

### **Basic Usage**

```bash
# List current user's workspaces within quiet hours
python agents/prune_workspaces.py

# Check all users (requires appropriate permissions)
python agents/prune_workspaces.py --all

# Target specific user
python agents/prune_workspaces.py --user "john.doe"
```

### **Custom Duration**

```bash
# Use 12-hour quiet hours period instead of default 8 hours
python agents/prune_workspaces.py --duration 12

# Use 4-hour quiet hours period
python agents/prune_workspaces.py --duration 4
```

### **Cleanup Operations**

```bash
# Dry run - see what would be stopped
python agents/prune_workspaces.py --cleanup --dry-run

# Actually stop workspaces in quiet hours
python agents/prune_workspaces.py --cleanup

# Cleanup with custom duration
python agents/prune_workspaces.py --cleanup --duration 10
```

### **JSON Output**

```bash
# Machine-readable output
python agents/prune_workspaces.py --json

# JSON output with cleanup
python agents/prune_workspaces.py --cleanup --json
```

## 📊 **Output Examples**

### **Human-Readable Output**

```
🌙 WORKSPACES WITHIN QUIET HOURS PERIODS (3)
================================================================================

👤 bjorn
   Quiet Hours: 13:32 (Europe/London)
   Current Period: 13:32 - 21:32
------------------------------------------------------------
Workspace    Template              Status    Created
-----------  --------------------  --------  ----------
AgentID      kubernetes-agent-id   running   2025-04-09
DevEnv       python-template       stopped   2025-10-01
TestSpace    nodejs-template       stopped   2025-10-02

👤 alice
   Quiet Hours: 18:00 (UTC)
   Current Period: 18:00 - 02:00
------------------------------------------------------------
Workspace    Template              Status    Created
-----------  --------------------  --------  ----------
WebApp       react-template        running   2025-09-15
```

### **Cleanup Output**

```
🛑 Cleaning up 2 running workspaces:
------------------------------------------------------------
  🛑 Stopping: bjorn/AgentID (kubernetes-agent-id) - running
     Owner: bjorn
     Reason: Pruned during quiet hours
     Result: ✅ Success
  🛑 Stopping: alice/WebApp (react-template) - running
     Owner: alice
     Reason: Pruned during quiet hours
     Result: ✅ Success

📊 Cleanup completed: 2/2 workspaces processed successfully
```

## ⚙️ **Configuration**

### **agents_config.json**

```json
{
  "prune_workspaces": {
    "enabled": true,
    "default_quiet_hours_duration": 8,
    "timezone": "UTC",
    "excluded_users": ["admin", "on-call-engineer"],
    "excluded_templates": ["production-template-id", "critical-service-template-id"]
  }
}
```

### **Configuration Options**

| Option | Description | Default |
|--------|-------------|---------|
| `enabled` | Enable/disable the prune workspaces agent | `true` |
| `default_quiet_hours_duration` | Default quiet hours duration in hours | `8` |
| `timezone` | Fallback timezone if user timezone unavailable | `"UTC"` |
| `excluded_users` | Users exempt from pruning | `["admin"]` |
| `excluded_templates` | Templates exempt from pruning | `[]` |

## 🔧 **Command Line Options**

| Option | Description | Example |
|--------|-------------|---------|
| `--user USER` | Target specific user | `--user "john.doe"` |
| `--all` | Check all users | `--all` |
| `--duration HOURS` | Quiet hours duration | `--duration 12` |
| `--cleanup` | Actually stop workspaces | `--cleanup` |
| `--dry-run` | Show what would be done | `--dry-run` |
| `--json` | JSON output format | `--json` |
| `--config FILE` | Custom config file | `--config my_config.json` |

## 🔧 **How It Works**

### **1. User Discovery**
- **Default**: Current user only
- **`--user`**: Specific user
- **`--all`**: All workspace owners (attempts to get quiet hours for each)

### **2. Quiet Hours Detection**
1. Fetch user's enterprise quiet hours schedule via API
2. Parse cron schedule: `CRON_TZ=UTC 0 18 * * *`
3. Extract start time (`18:00`) and timezone (`UTC`)
4. Calculate current quiet hours period based on baseline duration

### **3. Workspace Analysis**
1. Get all workspaces for target users
2. Filter by excluded users/templates
3. Check if current time falls within user's quiet hours period
4. Return matching workspaces with quiet hours metadata

### **4. Activity & Conflict Detection**
1. Check workspace activity levels and recent usage
2. Evaluate user's autostop settings and TTL configuration
3. Determine if workspace should be stopped immediately or extended
4. Apply conflict resolution priority (autostop > TTL > activity > quiet hours)

### **5. Cleanup (Optional)**
1. Filter to only running workspaces eligible for stopping
2. Respect activity detection and user preferences
3. Stop each workspace using Coder API with appropriate reasoning
4. Report success/failure for each operation with extension details

## 🛡️ **Safety Features**

### **Exclusions**
- **Users**: Protect admin users and on-call engineers
- **Templates**: Exclude production or critical templates
- **Status**: Only running workspaces are stopped during cleanup

### **Dry Run Mode**
```bash
# Safe testing - shows what would happen without executing
python agents/prune_workspaces.py --cleanup --dry-run
```

### **Error Handling**
- Graceful handling of users without quiet hours configured
- API error recovery with multiple stop reason attempts
- Detailed error reporting for failed operations

## 🕐 **Time Zone Handling**

### **User Timezone Priority**
1. **User's Enterprise Schedule**: `Europe/London` from `CRON_TZ=Europe/London 32 13 * * *`
2. **Config Fallback**: `timezone` setting in `agents_config.json`
3. **System Default**: `UTC`

### **Quiet Hours Calculation**
```python
# Example: User in London timezone
start_time = "18:00"  # From enterprise schedule (6 PM)
timezone = "UTC"  # From enterprise schedule
duration = 8  # From --duration parameter or config

# Current period calculation
quiet_start = today_at_18_00_utc  # 6 PM UTC
quiet_end = quiet_start + 8_hours  # 02:00 next day UTC (2 AM)

# Check if current time is within this period
is_in_quiet_hours = quiet_start <= current_utc_time <= quiet_end
```

## 📅 **Scheduling Examples**

### **Cron Jobs**

```bash
# Check for workspaces to prune every 30 minutes
*/30 * * * * python /path/to/agents/prune_workspaces.py --cleanup

# Daily report of workspaces in quiet hours
0 9 * * * python /path/to/agents/prune_workspaces.py --all --json > /var/log/quiet-hours-report.json

# Hourly check with 12-hour quiet hours duration
0 * * * * python /path/to/agents/prune_workspaces.py --duration 12 --cleanup
```

### **Systemd Timer**

```ini
# /etc/systemd/system/prune-workspaces.timer
[Unit]
Description=Prune workspaces in quiet hours
Requires=prune-workspaces.service

[Timer]
OnCalendar=*:0/30  # Every 30 minutes
Persistent=true

[Install]
WantedBy=timers.target
```

```ini
# /etc/systemd/system/prune-workspaces.service
[Unit]
Description=Prune Coder workspaces during quiet hours

[Service]
Type=oneshot
Environment=CODER_URL=https://your-coder-instance.com
Environment=CODER_TOKEN=your-api-token
ExecStart=/usr/bin/python3 /opt/coder-agents/agents/prune_workspaces.py --cleanup
User=coder-agent
```

## 🔗 **Integration with Other Agents**

### **Complementary Usage**
- **Quiet Hours Agent**: Global quiet hours policy enforcement
- **Prune Workspaces Agent**: User-specific quiet hours cleanup
- **TTL Monitor**: TTL-based compliance monitoring

### **Combined Workflow**
```bash
# 1. Check global quiet hours policy
python agents/quiet_hours_agent.py --status

# 2. Check user-specific quiet hours workspaces
python agents/prune_workspaces.py --all

# 3. Cleanup based on user preferences
python agents/prune_workspaces.py --cleanup --duration 10
```

## 🚨 **Troubleshooting**

### **Common Issues**

1. **No workspaces found**
   - User may not have quiet hours configured
   - Current time may be outside quiet hours period
   - Check user's enterprise schedule with `--json` output

2. **API errors during cleanup**
   - Verify API token permissions
   - Check workspace status (may already be stopped)
   - Review Coder API logs

3. **Timezone confusion**
   - Verify user's enterprise timezone setting
   - Use `--json` to see parsed quiet hours info
   - Check system timezone vs user timezone

### **Debug Commands**

```bash
# Check user's quiet hours configuration
python agents/enterprise_quiet_hours.py --user "username"

# See detailed workspace analysis
python agents/prune_workspaces.py --user "username" --json

# Test without cleanup
python agents/prune_workspaces.py --all --dry-run
```

## 🎯 **Use Cases**

### **1. Personal Workspace Management**
```bash
# Clean up my workspaces during my quiet hours
python agents/prune_workspaces.py --cleanup
```

### **2. Team Resource Optimization**
```bash
# Check all team members' workspaces
python agents/prune_workspaces.py --all --cleanup --dry-run
```

### **3. Custom Quiet Hours Duration**
```bash
# Use 12-hour quiet hours for weekend cleanup
python agents/prune_workspaces.py --duration 12 --cleanup
```

### **4. Automated Reporting**
```bash
# Generate daily report of quiet hours compliance
python agents/prune_workspaces.py --all --json > daily-quiet-hours-report.json
```

This agent provides flexible, user-centric workspace management that respects individual quiet hours preferences while maintaining organizational resource efficiency.