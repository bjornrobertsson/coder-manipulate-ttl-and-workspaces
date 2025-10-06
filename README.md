# Coder Workspace Management Agents

A comprehensive workspace management solution that extends the [coder-audit-simple](https://github.com/bjornrobertsson/coder-audit-simple) project with intelligent workspace stopping capabilities, TTL monitoring, and enterprise quiet hours integration.

## 🎯 **Features**

### 🌙 **Quiet Hours Agent**
- **Intelligent Stopping**: Automatically stops workspaces during configured quiet hours with grace period
- **Enterprise Integration**: Syncs with Coder's enterprise quiet hours policies
- **Workspace Categorization**: Detailed analysis of workspace states and stopping reasons
- **Force TTL Mode**: Option to stop TTL-expired workspaces regardless of quiet hours
- **Safety Features**: Dry-run mode, user exclusions, and comprehensive logging

### ⏱️ **TTL Monitor Agent**
- **Accurate Compliance**: Monitors workspace TTL settings with precise violation detection
- **Real-time Analysis**: Shows workspaces that should be stopped vs. already stopped
- **Predictive Monitoring**: Identifies workspaces expiring soon
- **Continuous Monitoring**: Daemon mode for ongoing TTL compliance tracking

### 🏢 **Enterprise Integration**
- **Enterprise Quiet Hours**: Full visibility into enterprise policies and user schedules
- **User Schedule Sync**: Automatic detection of individual user quiet hours settings
- **Policy Compliance**: Ensures agent alignment with enterprise configurations

## 🚀 **Quick Start**

### Installation
```bash
# Clone the repository
git clone git@github.com:bjornrobertsson/coder-manipulate-ttl-and-workspaces.git
cd coder-manipulate-ttl-and-workspaces

# Install dependencies
pip install -r requirements.txt

# Set environment variables
export CODER_URL=\"https://your-coder-instance.com\"
export CODER_TOKEN=\"your-api-token\"

# Test connection
python agents/workspace_controller.py
```

### Basic Usage

#### **Global Quiet Hours Management**
```bash
# Check quiet hours status with enterprise info
python agents/quiet_hours_agent.py --status

# Show detailed workspace categorization
python agents/quiet_hours_agent.py --categorize

# Execute quiet hours stopping (dry run)
python agents/quiet_hours_agent.py --execute --dry-run

# Force stop TTL-expired workspaces
python agents/quiet_hours_agent.py --execute --force
```

#### **User-Specific Quiet Hours (8-Hour Lifetime)**
```bash
# Check current user's workspaces in quiet hours (8-hour lifetime)
python agents/prune_workspaces.py

# Check all users with their individual quiet hours
python agents/prune_workspaces.py --all

# Custom 12-hour lifetime for development teams
python agents/prune_workspaces.py --duration 12 --cleanup --dry-run

# Organization-specific cleanup with 6-hour lifetime
python agents/prune_workspaces.py --include-org "engineering" --duration 6 --cleanup
```

#### **Monitoring and Reporting**
```bash
# Generate TTL compliance report
python agents/ttl_monitor_agent.py --report

# Show enterprise quiet hours configuration
python agents/enterprise_quiet_hours.py

# JSON output for automation
python agents/prune_workspaces.py --all --json
```

## 🌙 **Understanding Quiet Hours**

### **What Are Quiet Hours?**
Quiet Hours are designated time periods when workspaces should be automatically stopped to:
- **Reduce costs** by stopping unused development workspaces during off-hours
- **Enforce organizational policies** for resource management
- **Prevent workspace sprawl** and forgotten running instances
- **Align with team schedules** and working hours

### **The 8-Hour Lifetime Concept**

Unlike traditional quiet hours that only have a start/end time, our **Prune Workspaces Agent** introduces an **8-hour lifetime** concept to address real-world scenarios:

#### **Why 8-Hour Lifetime?**

**Traditional Quiet Hours Problem:**
- Standard quiet hours: `18:00 - 08:00` (14 hours)
- **Issue**: Workspaces started at `07:00` would be immediately stopped at `18:00` (only 11 hours of use)
- **Issue**: Workspaces started at `17:59` would run until `18:00` next day (24+ hours)

**8-Hour Lifetime Solution:**
- **Concept**: Workspaces get a guaranteed **8-hour lifetime** from their quiet hours start time
- **Example**: User's quiet hours start at `13:32`, workspace gets stopped at `21:32` (13:32 + 8 hours)
- **Benefit**: Consistent, predictable workspace lifetime regardless of when quiet hours start

#### **How It Works**

```
User's Quiet Hours: 13:32 London Time
8-Hour Lifetime: 13:32 → 21:32 (8 hours later)

Workspace Lifecycle:
├─ 13:32: Quiet hours period begins
├─ 13:32-21:32: Workspace allowed to run (8-hour lifetime)
└─ 21:32: Workspace eligible for stopping
```

#### **Edge Case Handling**

The system includes intelligent edge case handling:

1. **Midnight Boundary**: `+15 minutes before midnight`
   - Prevents workspaces from being stopped too close to midnight
   - Avoids day-boundary confusion

2. **Pre-Quiet Hours Buffer**: `+2 hours before quiet hours start`
   - Workspaces started shortly before quiet hours get reasonable runtime
   - Prevents immediate stopping of recently started workspaces

#### **Comparison: Traditional vs Lifetime Approach**

| Scenario | Traditional Quiet Hours | 8-Hour Lifetime |
|----------|------------------------|------------------|
| **Workspace started at 07:00** | Stopped at 18:00 (11h) | Stopped at 21:32 (8h from QH start) |
| **Workspace started at 17:59** | Stopped at 18:00 next day (24h+) | Stopped at 21:32 (8h from QH start) |
| **Workspace started at 20:00** | Stopped at 08:00 next day (12h) | Stopped at 21:32 (8h from QH start) |
| **Consistency** | ❌ Variable (11-24+ hours) | ✅ Predictable (8 hours) |

### **Quiet Hours vs Prune Workspaces**

| Feature | Quiet Hours Agent | Prune Workspaces Agent |
|---------|-------------------|------------------------|
| **Schedule Source** | Global configuration | Individual user enterprise schedules |
| **Duration** | Fixed start/end times | Configurable lifetime (default 8h) |
| **User Targeting** | All users (with exclusions) | User-specific quiet hours |
| **Enterprise Integration** | Basic | Full enterprise schedule sync |
| **Use Case** | Organization-wide policy | User-respectful management |

### **Practical Benefits of 8-Hour Lifetime**

#### **Cost Optimization**
- **Predictable Costs**: Workspaces run for consistent durations
- **No Surprise Bills**: Eliminates 24+ hour workspace runs
- **Fair Usage**: All users get equal workspace lifetime

#### **Developer Experience**
- **Predictable Shutdowns**: Developers know exactly when workspaces will stop
- **Timezone Respect**: Uses individual user's timezone settings
- **Work-Life Balance**: Aligns with personal quiet hours preferences

#### **Operational Benefits**
- **Reduced Support**: Fewer "why was my workspace stopped?" tickets
- **Consistent Behavior**: Same rules apply regardless of start time
- **Enterprise Compliance**: Respects individual user enterprise schedules

### **Real-World Example**

```
Scenario: Developer in London (bjorn)
├─ Enterprise Quiet Hours: 13:32 Europe/London
├─ 8-Hour Lifetime: 13:32 → 21:32 London time
├─ Workspace started at 10:00: Runs until 21:32 (11.5 hours)
├─ Workspace started at 15:00: Runs until 21:32 (6.5 hours)
└─ Workspace started at 20:00: Runs until 21:32 (1.5 hours)

Result: All workspaces stop at the same predictable time (21:32)
Benefit: Developer knows exactly when to save work and expect shutdown
```

## 📊 **Workspace Categorization**

The agents provide detailed categorization of all workspaces:

- 🛑 **Quiet Hours - Stopping Now**: Grace period over, ready to stop
- ⏰ **Quiet Hours - Grace Period**: In quiet hours but within grace period  
- 🌅 **Running Past Quiet Hours End**: Running beyond configured end time
- 💀 **TTL Expired - Should Have Stopped**: Exceeded configured TTL
- ✅ **Running Normally**: Operating within normal parameters
- 🚫 **Excluded from Quiet Hours**: Protected users/templates

## 🔧 **Configuration**

### Basic Configuration (`agents_config.json`)
```json
{
  \"quiet_hours\": {
    \"enabled\": true,
    \"start_time\": \"18:00\",
    \"end_time\": \"08:00\",
    \"timezone\": \"UTC\",
    \"grace_period_hours\": 1,
    \"excluded_users\": [\"admin\"],
    \"excluded_templates\": [\"production-template-id\"]
  },
  \"prune_workspaces\": {
    \"enabled\": true,
    \"default_quiet_hours_duration\": 8,
    \"timezone\": \"UTC\",
    \"include_organizations\": [],
    \"exclude_organizations\": [],
    \"include_groups\": [],
    \"exclude_groups\": [],
    \"include_users\": [],
    \"exclude_users\": [\"admin\", \"on-call-engineer\"],
    \"include_templates\": [],
    \"exclude_templates\": [\"production-template-id\"]
  },
  \"ttl_monitor\": {
    \"enabled\": true,
    \"warning_threshold_hours\": 1,
    \"check_interval_minutes\": 15
  }
}
```

### Quiet Hours Duration Configuration

```bash
# Use default 8-hour lifetime
python agents/prune_workspaces.py --cleanup

# Custom 12-hour lifetime for longer development sessions
python agents/prune_workspaces.py --duration 12 --cleanup

# Short 4-hour lifetime for quick tasks
python agents/prune_workspaces.py --duration 4 --cleanup

# Weekend mode with 16-hour lifetime
python agents/prune_workspaces.py --duration 16 --cleanup
```

### Environment Variables
```bash
export CODER_URL=\"https://your-coder-instance.com\"
export CODER_TOKEN=\"your-api-token\"
export QUIET_HOURS_START=\"18:00\"
export QUIET_HOURS_END=\"08:00\"
export QUIET_HOURS_TIMEZONE=\"UTC\"
```

## 📅 **Scheduling**

### Cron Jobs

#### **Global Quiet Hours (Organization-wide)**
```bash
# Check global quiet hours every 15 minutes
*/15 * * * * python /path/to/agents/quiet_hours_agent.py --execute

# Force stop TTL-expired workspaces every hour
0 * * * * python /path/to/agents/quiet_hours_agent.py --execute --force
```

#### **User-Specific Quiet Hours (8-Hour Lifetime)**
```bash
# Check user-specific quiet hours every 30 minutes
*/30 * * * * python /path/to/agents/prune_workspaces.py --all --cleanup

# Development teams with 12-hour lifetime (less frequent)
0 */2 * * * python /path/to/agents/prune_workspaces.py --include-org "engineering" --duration 12 --cleanup

# Quick cleanup for test environments (4-hour lifetime)
*/15 * * * * python /path/to/agents/prune_workspaces.py --include-template "test-env" --duration 4 --cleanup
```

#### **Monitoring and Reporting**
```bash
# Generate TTL report every hour
0 * * * * python /path/to/agents/ttl_monitor_agent.py --report

# Daily enterprise quiet hours report
0 9 * * * python /path/to/agents/enterprise_quiet_hours.py --json > /var/log/enterprise-qh-$(date +\%Y\%m\%d).json

# Monitor TTL compliance continuously
@reboot python /path/to/agents/ttl_monitor_agent.py --monitor
```

### Systemd Service
```ini
[Unit]
Description=Coder Workspace Management Agents
After=network.target

[Service]
Type=simple
User=coder-agent
WorkingDirectory=/opt/coder-agents
Environment=CODER_URL=https://your-coder-instance.com
Environment=CODER_TOKEN=your-api-token
ExecStart=/usr/bin/python3 agents/quiet_hours_agent.py --execute
Restart=always
RestartSec=300

[Install]
WantedBy=multi-user.target
```

## 📖 **Documentation**

- **[AGENTS.md](AGENTS.md)** - Complete documentation for the workspace management extension
- **[agents/README.md](agents/README.md)** - Quick start guide for the agents
- **[PROJECT_STRUCTURE.md](PROJECT_STRUCTURE.md)** - Project organization and architecture
- **[ENHANCED_QUIET_HOURS_FEATURES.md](ENHANCED_QUIET_HOURS_FEATURES.md)** - Detailed feature documentation
- **[ENTERPRISE_QUIET_HOURS_ANALYSIS.md](ENTERPRISE_QUIET_HOURS_ANALYSIS.md)** - Enterprise integration guide

## 🛡️ **Safety Features**

- **Dry Run Mode**: Test all operations safely without executing changes
- **User Exclusions**: Protect admin users and critical workspaces
- **Template Exclusions**: Exclude production or critical templates
- **Rate Limiting**: Prevent API overload with configurable limits
- **Error Handling**: Comprehensive error recovery and logging
- **Connection Validation**: Verify API connectivity before operations

## 🔍 **API Integration**

### Coder API Endpoints Used
- `GET /api/v2/workspaces` - List workspaces
- `GET /api/v2/templates` - List templates
- `GET /api/v2/deployment/config` - Enterprise configuration
- `GET /api/v2/users/me/quiet-hours` - User quiet hours schedule
- `POST /api/v2/workspaces/{id}/builds` - Stop workspace
- `PUT /api/v2/workspaces/{id}/ttl` - Update TTL

### Authentication
Uses `Coder-Session-Token` header for API authentication, compatible with existing coder-audit-simple patterns.

## 🎯 **Use Cases**

### 1. **Automated Resource Management**
- Reduce compute costs during off-hours
- Enforce organizational quiet hours policies
- Prevent workspace sprawl and resource waste

### 2. **Compliance and Governance**
- Monitor TTL policy compliance
- Generate compliance reports for auditing
- Ensure workspaces don't run indefinitely

### 3. **Operational Efficiency**
- Reduce manual workspace management overhead
- Provide detailed visibility into workspace lifecycle
- Automate routine cleanup operations

## 🤝 **Contributing**

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📝 **License**

This project extends the coder-audit-simple project and maintains compatibility with its licensing.

## 🔗 **Related Projects**

- [coder-audit-simple](https://github.com/bjornrobertsson/coder-audit-simple) - Original audit functionality
- [Coder](https://github.com/coder/coder) - The Coder platform

## 📞 **Support**

For issues, questions, or contributions, please open an issue in this repository or refer to the comprehensive documentation in the `docs/` directory.

---

**Built with ❤️ for the Coder community**