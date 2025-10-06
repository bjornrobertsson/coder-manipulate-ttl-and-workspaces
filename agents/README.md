# Coder Workspace Management Agents

This directory contains intelligent agents for managing Coder workspaces based on various policies and schedules.

## Quick Start

1. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Set Environment Variables**:
   ```bash
   export CODER_URL="https://your-coder-instance.com"
   export CODER_TOKEN="your-api-token"
   ```

3. **Test Connection**:
   ```bash
   python workspace_controller.py
   ```

## Available Agents

### 1. Quiet Hours Agent (`quiet_hours_agent.py`)
Automatically stops workspaces during configured quiet hours with a grace period. Now includes workspace categorization and force-stop for TTL-expired workspaces.

```bash
# Check status with enterprise info
python quiet_hours_agent.py --status

# Show detailed workspace categorization
python quiet_hours_agent.py --categorize

# Dry run (see what would be stopped)
python quiet_hours_agent.py --execute --dry-run

# Execute quiet hours stopping
python quiet_hours_agent.py --execute

# Force stop TTL-expired workspaces too
python quiet_hours_agent.py --execute --force

# Test force mode safely
python quiet_hours_agent.py --execute --force --dry-run
```

### 2. TTL Monitor Agent (`ttl_monitor_agent.py`)
Monitors workspace TTL compliance and identifies workspaces that should have stopped.

```bash
# Generate compliance report
python ttl_monitor_agent.py --report

# Monitor specific user
python ttl_monitor_agent.py --user "john.doe"

# Continuous monitoring
python ttl_monitor_agent.py --monitor
```

### 3. Workspace Controller (`workspace_controller.py`)
Core API wrapper for workspace control operations.

```bash
# Test connection and list running workspaces
python workspace_controller.py
```

### 4. Enterprise Quiet Hours Checker (`enterprise_quiet_hours.py`)
Display enterprise and user quiet hours configuration.

```bash
# Show enterprise quiet hours configuration
python enterprise_quiet_hours.py

# Output in JSON format
python enterprise_quiet_hours.py --json

# Check specific user's quiet hours (requires admin privileges)
python enterprise_quiet_hours.py --user "username"
```

### 5. Prune Workspaces Agent (`prune_workspaces.py`)
Identify and cleanup workspaces within user-specific quiet hours periods with comprehensive filtering by organizations, groups, users, and templates.

```bash
# Basic usage - current user's workspaces
python prune_workspaces.py

# Check all users' workspaces
python prune_workspaces.py --all

# Organization-based filtering
python prune_workspaces.py --include-org "engineering" --exclude-org "production"

# Group-based filtering
python prune_workspaces.py --include-group "developers" --exclude-group "on-call"

# User-based filtering
python prune_workspaces.py --include-user "john.doe" --exclude-user "admin"

# Template-based filtering
python prune_workspaces.py --include-template "python-dev" --exclude-template "production-api"

# Combined filtering with cleanup
python prune_workspaces.py \\
  --include-org "engineering" \\
  --exclude-group "administrators" \\
  --exclude-template "critical-service" \\
  --cleanup --dry-run

# Custom quiet hours duration
python prune_workspaces.py --duration 12 --cleanup

# JSON output for automation
python prune_workspaces.py --all --json
```

## Configuration

Edit `agents_config.json` to customize agent behavior:

```json
{
  "quiet_hours": {
    "start_time": "18:00",
    "end_time": "08:00",
    "grace_period_hours": 1,
    "excluded_users": ["admin"]
  },
  "ttl_monitor": {
    "warning_threshold_hours": 1
  }
}
```

## Scheduling

### Cron Examples

```bash
# Check quiet hours every 15 minutes
*/15 * * * * python /path/to/agents/quiet_hours_agent.py --execute

# Generate TTL report every hour
0 * * * * python /path/to/agents/ttl_monitor_agent.py --report
```

## Safety Features

- **Dry Run Mode**: Test operations without executing them
- **User Exclusions**: Protect admin users and critical workspaces
- **Rate Limiting**: Prevent API overload
- **Error Handling**: Robust error recovery and logging

## Extending the Agents

The agents are designed to be extensible. Key patterns:

1. **Inherit from Base Classes**: Use `WorkspaceController` for API operations
2. **Configuration-Driven**: Use JSON config files for flexibility
3. **CLI Interface**: Provide command-line interfaces for all agents
4. **Error Handling**: Implement comprehensive error handling and logging

## Troubleshooting

### Common Issues

1. **Connection Errors**: Check `CODER_URL` and `CODER_TOKEN`
2. **Permission Denied**: Ensure API token has workspace management permissions
3. **Configuration Errors**: Validate JSON syntax in config files

### Debug Mode

Run with verbose output:
```bash
python quiet_hours_agent.py --status --verbose
```

### Logs

Check agent logs in the configured log file (default: `agents.log`).