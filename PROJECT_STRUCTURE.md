# Coder Workspace Management - Project Structure

This document shows the complete project structure after extending the [coder-audit-simple](https://github.com/bjornrobertsson/coder-audit-simple) project with workspace stopping capabilities.

## Directory Structure

```
coder-audit-simple/                 # Original project (cloned)
├── coder_audit.py                  # Original: Basic workspace auditing
├── coder_dashboard.py              # Original: Activity dashboard
├── get_and_bump_ttl_workspaces.py  # Original: TTL management
├── last_seen_monitor.py            # Original: User activity monitoring
├── connect_count.py                # Original: Connection counting
├── coder-last.py                   # Original: Last activity tracking
├── bash-version-dormancy.sh        # Original: Bash version
└── README.md                       # Original: Basic documentation

Audit-and-stop/                     # Extended project root
├── AGENTS.md                       # 📋 Main documentation (this file)
├── PROJECT_STRUCTURE.md            # 📁 Project structure overview
├── install.sh                      # 🚀 Installation script
├── requirements.txt                # 📦 Python dependencies
├── agents_config.json              # ⚙️ Configuration file
├── cron-examples.txt               # ⏰ Cron job examples (generated)
├── coder-agents.service             # 🔧 Systemd service template (generated)
│
└── agents/                         # 🤖 New: Workspace management agents
    ├── README.md                   # 📖 Agents documentation
    ├── workspace_controller.py     # 🎮 Core API wrapper
    ├── quiet_hours_agent.py        # 🌙 Quiet hours management
    ├── ttl_monitor_agent.py        # ⏱️ TTL compliance monitoring
    ├── autostop_agent.py           # 🛑 AutoStop policy management (planned)
    └── example_usage.py            # 🧪 Usage examples and demos
```

## File Descriptions

### Core Documentation
- **`AGENTS.md`** - Main documentation for the workspace management extension
- **`PROJECT_STRUCTURE.md`** - This file, showing project organization
- **`agents/README.md`** - Quick start guide for the agents

### Configuration & Setup
- **`agents_config.json`** - Central configuration for all agents
- **`requirements.txt`** - Python package dependencies
- **`install.sh`** - Automated installation and setup script

### Core Agents
- **`workspace_controller.py`** - Base class for Coder API operations
- **`quiet_hours_agent.py`** - Manages workspaces during quiet hours
- **`ttl_monitor_agent.py`** - Monitors TTL compliance and violations

### Utilities & Examples
- **`example_usage.py`** - Demonstrates how to use the agents programmatically
- **`cron-examples.txt`** - Example cron jobs for scheduling (auto-generated)
- **`coder-agents.service`** - Systemd service template (auto-generated)

## Key Features Implemented

### 1. Quiet Hours Management ✅
- **File**: `agents/quiet_hours_agent.py`
- **Purpose**: Stop workspaces 1 hour after quiet hours start
- **Features**:
  - Configurable quiet hours schedule
  - Grace period before stopping
  - User and template exclusions
  - Dry-run mode for testing
  - Timezone support

### 2. TTL Monitoring ✅
- **File**: `agents/ttl_monitor_agent.py`
- **Purpose**: Monitor TTL compliance and predict stopping times
- **Features**:
  - Real-time TTL analysis
  - "Should have stopped" detection
  - "Will stop soon" predictions
  - Compliance reporting
  - Continuous monitoring mode

### 3. Workspace Control API ✅
- **File**: `agents/workspace_controller.py`
- **Purpose**: Core API wrapper for workspace operations
- **Features**:
  - Workspace stopping functionality
  - Bulk operations with rate limiting
  - Error handling and retries
  - Connection validation
  - Template mapping

### 4. AutoStop Management 🔄
- **File**: `agents/autostop_agent.py` (planned)
- **Purpose**: Manage AutoStop policies and schedules
- **Features** (planned):
  - AutoStop policy detection
  - Scheduled stopping timeline
  - Batch stopping operations
  - User notifications

## API Endpoints Used

### Existing (from coder-audit-simple)
- `GET /api/v2/workspaces` - List workspaces
- `GET /api/v2/templates` - List templates
- `GET /api/v2/audit` - Audit logs
- `PUT /api/v2/workspaces/{id}/ttl` - Update TTL

### New (for stopping functionality)
- `POST /api/v2/workspaces/{id}/builds` - Stop workspace
- `GET /api/v2/workspaces/{id}` - Get workspace details
- `GET /api/v2/workspaces/{id}/builds/{build_id}` - Build status

## Configuration Structure

```json
{
  "quiet_hours": {
    "enabled": true,
    "start_time": "18:00",
    "end_time": "08:00",
    "timezone": "UTC",
    "grace_period_hours": 1,
    "excluded_users": ["admin"],
    "excluded_templates": ["production-template-id"]
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
  "safety": {
    "max_stops_per_minute": 10,
    "emergency_stop_enabled": true
  }
}
```

## Usage Examples

### Command Line Usage
```bash
# Quiet Hours Agent
python agents/quiet_hours_agent.py --status
python agents/quiet_hours_agent.py --dry-run
python agents/quiet_hours_agent.py --execute

# TTL Monitor Agent  
python agents/ttl_monitor_agent.py --report
python agents/ttl_monitor_agent.py --user "john.doe"
python agents/ttl_monitor_agent.py --monitor

# Workspace Controller
python agents/workspace_controller.py
```

### Programmatic Usage
```python
from agents.workspace_controller import WorkspaceController
from agents.quiet_hours_agent import QuietHoursAgent
from agents.ttl_monitor_agent import TTLMonitorAgent

# Initialize agents
controller = WorkspaceController()
quiet_agent = QuietHoursAgent()
ttl_agent = TTLMonitorAgent()

# Get running workspaces
running = controller.get_running_workspaces()

# Check quiet hours status
if quiet_agent.is_grace_period_over():
    results = quiet_agent.stop_workspaces_for_quiet_hours()

# Generate TTL report
report = ttl_agent.get_ttl_compliance_report()
```

## Scheduling Options

### Cron Jobs
```bash
# Check quiet hours every 15 minutes
*/15 * * * * python /path/to/agents/quiet_hours_agent.py --execute

# Generate TTL report every hour
0 * * * * python /path/to/agents/ttl_monitor_agent.py --report
```

### Systemd Service
```ini
[Unit]
Description=Coder Workspace Management Agents

[Service]
ExecStart=/usr/bin/python3 agents/quiet_hours_agent.py --execute
Restart=always
RestartSec=300
```

## Safety Features

1. **Dry Run Mode** - Test operations without executing them
2. **User Exclusions** - Protect admin users and critical workspaces  
3. **Rate Limiting** - Prevent API overload
4. **Error Handling** - Robust error recovery and logging
5. **Rollback Capabilities** - Emergency recovery functions
6. **Connection Validation** - Verify API connectivity before operations

## Integration with Original Project

The extension maintains full compatibility with the original `coder-audit-simple` project:

1. **Shared Dependencies** - Uses same libraries (requests, tabulate)
2. **Common Patterns** - Follows existing code style and structure
3. **API Consistency** - Uses same authentication and endpoint patterns
4. **Configuration** - Extends existing token and URL management

## Future Enhancements

1. **Web Dashboard** - Browser-based management interface
2. **Advanced Notifications** - Slack/Teams integration
3. **Machine Learning** - Predictive stopping based on usage patterns
4. **Cost Optimization** - Cloud provider cost tracking
5. **Policy Engine** - Complex rule-based stopping policies

## Getting Started

1. **Clone and Install**:
   ```bash
   git clone https://github.com/bjornrobertsson/coder-audit-simple.git
   cd coder-audit-simple
   # Copy the extended files to this directory
   ./install.sh
   ```

2. **Configure**:
   ```bash
   export CODER_URL="https://your-coder-instance.com"
   export CODER_TOKEN="your-api-token"
   ```

3. **Test**:
   ```bash
   python agents/example_usage.py
   ```

4. **Deploy**:
   ```bash
   # Add to crontab
   crontab -e
   # Copy from cron-examples.txt
   ```

This structure provides a comprehensive workspace management solution while maintaining compatibility with the original audit functionality.