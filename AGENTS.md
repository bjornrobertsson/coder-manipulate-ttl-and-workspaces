# AGENTS.md - Coder Workspace Management Agents

## Overview

This document outlines the extension of the [coder-audit-simple](https://github.com/bjornrobertsson/coder-audit-simple) project to include intelligent workspace stopping capabilities. The project provides automated agents for managing Coder workspaces based on quiet hours, TTL policies, and AutoStop configurations.

## Project Structure

```
coder-audit-simple/
├── coder_audit.py              # Base workspace auditing functionality
├── coder_dashboard.py          # Comprehensive activity dashboard
├── get_and_bump_ttl_workspaces.py  # TTL management utilities
├── last_seen_monitor.py        # User activity monitoring
└── agents/                     # New: Workspace management agents
    ├── quiet_hours_agent.py    # Quiet hours detection and stopping
    ├── ttl_monitor_agent.py     # TTL-based workspace monitoring
    ├── autostop_agent.py        # AutoStop policy management
    └── workspace_controller.py  # Core workspace control API
```

## Core Agents

### 1. Quiet Hours Agent (`quiet_hours_agent.py`)

**Purpose**: Detect quiet hours and automatically stop workspaces 1 hour after quiet hours begin.

**Key Features**:
- Configurable quiet hours schedule (default: 6 PM - 8 AM)
- Grace period before stopping workspaces (default: 1 hour)
- Timezone-aware scheduling
- Dry-run mode for testing
- Notification system for affected users

**Configuration**:
```python
QUIET_HOURS_CONFIG = {
    "start_time": "18:00",      # 6 PM
    "end_time": "08:00",        # 8 AM
    "timezone": "UTC",          # Configurable timezone
    "grace_period_hours": 1,    # Hours to wait before stopping
    "excluded_users": [],       # Users exempt from quiet hours
    "excluded_templates": [],   # Templates exempt from quiet hours
    "dry_run": False           # Set to True for testing
}
```

**API Endpoints Used**:
- `GET /api/v2/workspaces` - List all workspaces
- `POST /api/v2/workspaces/{workspace}/builds` - Stop workspace
- `GET /api/v2/templates` - Get template information

### 2. TTL Monitor Agent (`ttl_monitor_agent.py`)

**Purpose**: Monitor workspace TTL settings and display which workspaces would or should have stopped.

**Key Features**:
- Real-time TTL monitoring
- Predictive stopping analysis
- TTL policy compliance reporting
- Historical TTL violation tracking
- Customizable TTL thresholds

**Functionality**:
```python
def analyze_ttl_compliance():
    """
    Analyzes workspace TTL compliance and predicts stopping times
    Returns:
    - Workspaces that should have stopped (TTL expired)
    - Workspaces that will stop soon (within threshold)
    - TTL policy violations
    """
```

**Report Format**:
```
TTL Compliance Report
=====================
Workspaces that SHOULD HAVE STOPPED:
- user1/workspace1: Expired 2h 30m ago (TTL: 8h)
- user2/workspace2: Expired 45m ago (TTL: 4h)

Workspaces STOPPING SOON:
- user3/workspace3: Stopping in 15m (TTL: 8h)
- user4/workspace4: Stopping in 1h 20m (TTL: 12h)
```

### 3. AutoStop Agent (`autostop_agent.py`)

**Purpose**: Manage AutoStop policies and display workspaces bound to be stopped with timing information.

**Key Features**:
- AutoStop policy detection
- Scheduled stopping timeline
- Policy conflict resolution
- Batch stopping operations
- User notification system

**Core Functions**:
```python
def get_autostop_workspaces():
    """
    Returns list of workspaces with AutoStop enabled
    Including: workspace info, stop time, policy details
    """

def display_autostop_schedule():
    """
    Shows when each AutoStop-enabled workspace will be stopped
    """

def execute_autostop_batch():
    """
    Executes scheduled AutoStop operations
    """
```

### 4. Workspace Controller (`workspace_controller.py`)

**Purpose**: Core API wrapper for workspace control operations.

**Key Methods**:
```python
class WorkspaceController:
    def __init__(self, coder_url, token):
        """Initialize with Coder API credentials"""
    
    def stop_workspace(self, workspace_id, reason="Automated stop"):
        """Stop a specific workspace"""
    
    def get_workspace_status(self, workspace_id):
        """Get current workspace status"""
    
    def bulk_stop_workspaces(self, workspace_ids, reason="Bulk stop"):
        """Stop multiple workspaces"""
    
    def get_running_workspaces(self, filters=None):
        """Get all running workspaces with optional filters"""
    
    def notify_users(self, workspace_ids, message):
        """Send notifications to workspace owners"""
```

## API Integration

### Existing API Usage Patterns

Based on the current codebase analysis, the project uses these Coder API endpoints:

1. **Authentication**: `Coder-Session-Token` header
2. **Workspaces**: `GET /api/v2/workspaces`
3. **Templates**: `GET /api/v2/templates`
4. **Audit Logs**: `GET /api/v2/audit`
5. **TTL Management**: `PUT /api/v2/workspaces/{id}/ttl`

### New API Endpoints for Stopping

```python
# Stop workspace by triggering a stop build
POST /api/v2/workspaces/{workspace_id}/builds
{
    "transition": "stop",
    "reason": "Automated stop - quiet hours"
}

# Get workspace build status
GET /api/v2/workspaces/{workspace_id}/builds/{build_id}

# Bulk operations (if supported)
POST /api/v2/workspaces/bulk-action
{
    "action": "stop",
    "workspace_ids": ["id1", "id2", "id3"],
    "reason": "Bulk stop operation"
}
```

## Configuration Management

### Environment Variables
```bash
# Required
export CODER_URL="https://your-coder-instance.com"
export CODER_TOKEN="your-api-token"

# Optional
export QUIET_HOURS_START="18:00"
export QUIET_HOURS_END="08:00"
export QUIET_HOURS_TIMEZONE="America/New_York"
export GRACE_PERIOD_HOURS="1"
export DRY_RUN="false"
```

### Configuration File (`agents_config.json`)
```json
{
    "quiet_hours": {
        "enabled": true,
        "start_time": "18:00",
        "end_time": "08:00",
        "timezone": "UTC",
        "grace_period_hours": 1,
        "excluded_users": ["admin", "on-call"],
        "excluded_templates": ["production", "critical"]
    },
    "ttl_monitor": {
        "enabled": true,
        "warning_threshold_hours": 1,
        "check_interval_minutes": 15
    },
    "autostop": {
        "enabled": true,
        "batch_size": 10,
        "notification_enabled": true
    },
    "notifications": {
        "email_enabled": false,
        "slack_webhook": "",
        "teams_webhook": ""
    }
}
```

## Usage Examples

### 1. Quiet Hours Agent
```bash
# Run quiet hours check (dry run)
python agents/quiet_hours_agent.py --dry-run

# Execute quiet hours stopping
python agents/quiet_hours_agent.py --execute

# Check specific timezone
python agents/quiet_hours_agent.py --timezone "America/New_York"
```

### 2. TTL Monitor
```bash
# Generate TTL compliance report
python agents/ttl_monitor_agent.py --report

# Monitor specific user
python agents/ttl_monitor_agent.py --user "john.doe"

# Check workspaces expiring in next 2 hours
python agents/ttl_monitor_agent.py --threshold 2h
```

### 3. AutoStop Agent
```bash
# Show AutoStop schedule
python agents/autostop_agent.py --schedule

# Execute pending AutoStop operations
python agents/autostop_agent.py --execute

# Show workspaces bound to be stopped
python agents/autostop_agent.py --list-pending
```

## Scheduling and Automation

### Cron Job Examples
```bash
# Check quiet hours every 15 minutes
*/15 * * * * /usr/bin/python3 /path/to/agents/quiet_hours_agent.py --execute

# Generate TTL report every hour
0 * * * * /usr/bin/python3 /path/to/agents/ttl_monitor_agent.py --report

# Execute AutoStop operations every 30 minutes
*/30 * * * * /usr/bin/python3 /path/to/agents/autostop_agent.py --execute
```

### Systemd Service Example
```ini
[Unit]
Description=Coder Workspace Management Agents
After=network.target

[Service]
Type=simple
User=coder-agent
WorkingDirectory=/opt/coder-agents
ExecStart=/usr/bin/python3 -m agents.scheduler
Restart=always
RestartSec=30

[Install]
WantedBy=multi-user.target
```

## Monitoring and Logging

### Log Format
```
2024-01-15 18:00:00 [QUIET_HOURS] INFO: Quiet hours started, grace period until 19:00:00
2024-01-15 18:00:01 [QUIET_HOURS] INFO: Found 15 running workspaces
2024-01-15 18:00:02 [QUIET_HOURS] INFO: Excluded 2 workspaces (admin users)
2024-01-15 19:00:00 [QUIET_HOURS] INFO: Grace period ended, stopping 13 workspaces
2024-01-15 19:00:01 [WORKSPACE] INFO: Stopped workspace user1/dev-env (reason: quiet hours)
2024-01-15 19:00:02 [WORKSPACE] ERROR: Failed to stop workspace user2/test-env (API error)
```

### Metrics Collection
```python
METRICS = {
    "workspaces_stopped_quiet_hours": 0,
    "workspaces_stopped_ttl": 0,
    "workspaces_stopped_autostop": 0,
    "api_errors": 0,
    "notification_failures": 0
}
```

## Safety Features

### 1. Dry Run Mode
All agents support `--dry-run` flag to preview actions without executing them.

### 2. User Exclusions
- Admin users can be excluded from automatic stopping
- Critical templates can be protected
- Emergency override mechanisms

### 3. Rollback Capabilities
```python
def emergency_start_all():
    """Emergency function to start all recently stopped workspaces"""
    
def rollback_last_operation():
    """Rollback the last bulk stop operation"""
```

### 4. Rate Limiting
- Maximum workspaces stopped per minute
- API call rate limiting
- Exponential backoff for failures

## Error Handling

### Common Error Scenarios
1. **API Authentication Failures**: Retry with exponential backoff
2. **Workspace Already Stopped**: Log and continue
3. **Network Timeouts**: Retry up to 3 times
4. **Permission Denied**: Log error and notify administrators

### Error Recovery
```python
def handle_api_error(error, workspace_id, operation):
    """
    Centralized error handling for API operations
    - Log error details
    - Attempt recovery if possible
    - Notify administrators for critical errors
    """
```

## Testing

### Unit Tests
```bash
# Run all agent tests
python -m pytest tests/

# Test specific agent
python -m pytest tests/test_quiet_hours_agent.py

# Integration tests
python -m pytest tests/integration/
```

### Mock API Server
For testing purposes, include a mock Coder API server that simulates workspace operations.

## Security Considerations

1. **Token Management**: Store API tokens securely, rotate regularly
2. **Audit Logging**: Log all workspace stop operations
3. **Access Control**: Restrict agent execution to authorized users
4. **Network Security**: Use HTTPS for all API communications

## Migration from Existing Code

### Step 1: Extract Common Functions
Move shared utilities from existing files to a common module:
- API authentication
- Date/time formatting
- Workspace filtering

### Step 2: Extend Current Scripts
Enhance existing scripts with stopping capabilities:
- Add stop functionality to `coder_audit.py`
- Extend `get_and_bump_ttl_workspaces.py` with TTL-based stopping

### Step 3: Implement New Agents
Create new agent modules while maintaining compatibility with existing scripts.

## Future Enhancements

1. **Machine Learning**: Predict optimal stopping times based on usage patterns
2. **Integration**: Slack/Teams notifications, calendar integration
3. **Advanced Policies**: Complex stopping rules based on multiple criteria
4. **Dashboard**: Web interface for managing agents and viewing reports
5. **Cost Optimization**: Integration with cloud provider APIs for cost tracking

## Contributing

1. Follow existing code style and patterns
2. Add comprehensive tests for new functionality
3. Update documentation for any API changes
4. Ensure backward compatibility with existing scripts

## License

This extension maintains the same license as the original coder-audit-simple project.