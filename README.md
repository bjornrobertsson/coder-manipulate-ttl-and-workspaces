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
```bash
# Check quiet hours status with enterprise info
python agents/quiet_hours_agent.py --status

# Show detailed workspace categorization
python agents/quiet_hours_agent.py --categorize

# Execute quiet hours stopping (dry run)
python agents/quiet_hours_agent.py --execute --dry-run

# Force stop TTL-expired workspaces
python agents/quiet_hours_agent.py --execute --force

# Generate TTL compliance report
python agents/ttl_monitor_agent.py --report

# Show enterprise quiet hours configuration
python agents/enterprise_quiet_hours.py
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
  \"ttl_monitor\": {
    \"enabled\": true,
    \"warning_threshold_hours\": 1,
    \"check_interval_minutes\": 15
  }
}
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
```bash
# Check quiet hours every 15 minutes
*/15 * * * * python /path/to/agents/quiet_hours_agent.py --execute

# Generate TTL report every hour
0 * * * * python /path/to/agents/ttl_monitor_agent.py --report

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