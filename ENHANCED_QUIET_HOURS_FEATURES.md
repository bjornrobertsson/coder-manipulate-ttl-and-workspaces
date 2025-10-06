# Enhanced Quiet Hours Agent Features

## 🎯 **New Features Added**

The quiet hours agent has been significantly enhanced with workspace categorization and force-stop capabilities for TTL-expired workspaces.

### 1. **Workspace Categorization**

The agent now categorizes all running workspaces into distinct groups:

#### 🛑 **Quiet Hours - Stopping Now**
- Workspaces that are currently in quiet hours with grace period over
- These will be stopped immediately during `--execute`

#### ⏰ **Quiet Hours - Grace Period**  
- Workspaces in quiet hours but still within the grace period
- Will be stopped when grace period expires

#### 🌅 **Running Past Quiet Hours End**
- Workspaces that are running beyond the configured quiet hours end time
- May indicate workspaces that were manually started or extended

#### 💀 **TTL Expired - Should Have Stopped**
- Workspaces that have exceeded their configured TTL
- Can be force-stopped using the `--force` flag

#### ✅ **Running Normally**
- Workspaces running within normal parameters
- Not affected by quiet hours or TTL policies

#### 🚫 **Excluded from Quiet Hours**
- Workspaces belonging to excluded users or templates
- Protected from automatic quiet hours stopping

### 2. **Force Stop TTL-Expired Workspaces**

New `--force` flag allows stopping workspaces that have exceeded their TTL, regardless of quiet hours status.

## 🚀 **Usage Examples**

### Basic Commands

```bash
# Show detailed workspace categorization
python agents/quiet_hours_agent.py --categorize

# Execute quiet hours stopping (normal mode)
python agents/quiet_hours_agent.py --execute

# Execute with force stop for TTL-expired workspaces
python agents/quiet_hours_agent.py --execute --force

# Dry run with force (safe testing)
python agents/quiet_hours_agent.py --execute --force --dry-run
```

### Command Combinations

```bash
# Test what would happen with force mode
python agents/quiet_hours_agent.py --execute --force --dry-run

# Show categorization and then execute
python agents/quiet_hours_agent.py --categorize
python agents/quiet_hours_agent.py --execute --force

# Check status with enterprise info
python agents/quiet_hours_agent.py --status
```

## 📊 **Enhanced Output Examples**

### Workspace Categorization Output

```
================================================================================
WORKSPACE CATEGORIZATION
================================================================================

🛑 QUIET HOURS - STOPPING NOW (2)
------------------------------------------------------------
  • user1/dev-workspace (python-template) - running
    TTL: 2h 15m
  • user2/test-env (nodejs-template) - running
    TTL: 1h 30m

⏰ QUIET HOURS - GRACE PERIOD (1)
------------------------------------------------------------
  • user3/staging (docker-template) - running
    TTL: 45m

💀 TTL EXPIRED - SHOULD HAVE STOPPED (1)
------------------------------------------------------------
  • user4/old-workspace (legacy-template) - running
    TTL: Expired 2h 30m ago

✅ RUNNING NORMALLY (3)
------------------------------------------------------------
  • user5/morning-work (python-template) - running
    TTL: 6h 45m
  • user6/active-dev (react-template) - running
    TTL: 4h 20m
  • user7/research (jupyter-template) - running
    TTL: 8h 10m

🚫 EXCLUDED FROM QUIET HOURS (1)
------------------------------------------------------------
  • admin/production-monitor (monitoring-template) - running
    Reason: User excluded
================================================================================
```

### Enhanced Execute Output

```
🧪 [DRY RUN] Stopping 3 workspaces:
------------------------------------------------------------
  🧪 [DRY RUN] Would stop: user1/dev-workspace (python-template) - running
     Reason: Quiet hours policy
     TTL: 2h 15m
  🧪 [DRY RUN] Would stop: user2/test-env (nodejs-template) - running
     Reason: Quiet hours policy
     TTL: 1h 30m
  🧪 [DRY RUN] Would stop: user4/old-workspace (legacy-template) - running
     Reason: TTL expired
     TTL: Expired 2h 30m ago

📊 Operation completed: 3/3 workspaces stopped successfully
```

## 🔧 **Technical Implementation**

### New Methods Added

1. **`categorize_workspaces()`** - Analyzes all workspaces and categorizes them
2. **`print_workspace_categories()`** - Displays categorized workspace information
3. **`get_ttl_expired_workspaces()`** - Returns workspaces with expired TTL
4. **`is_past_quiet_hours_end()`** - Checks if past quiet hours end time
5. **`_format_time_remaining()`** - Formats TTL remaining time with expiration status

### Enhanced Methods

1. **`stop_workspaces_for_quiet_hours(force_ttl=False)`** - Now supports force mode
2. **Command line parser** - Added `--force` and `--categorize` flags

## 🎯 **Use Cases**

### 1. **Regular Quiet Hours Management**
```bash
# Daily automated execution
python agents/quiet_hours_agent.py --execute
```

### 2. **Aggressive Resource Cleanup**
```bash
# Stop both quiet hours and TTL-expired workspaces
python agents/quiet_hours_agent.py --execute --force
```

### 3. **Monitoring and Reporting**
```bash
# Generate detailed workspace status report
python agents/quiet_hours_agent.py --categorize
```

### 4. **Safe Testing**
```bash
# Test what would happen without actually stopping
python agents/quiet_hours_agent.py --execute --force --dry-run
```

## ⚠️ **Important Notes**

### Force Mode Behavior
- `--force` stops TTL-expired workspaces **in addition to** quiet hours workspaces
- TTL-expired workspaces are stopped regardless of quiet hours status
- Excluded users and templates are still respected
- Dry run mode works with force mode for safe testing

### TTL Expiration Detection
- Uses workspace `deadline` field from latest build
- Compares against current UTC time
- Shows human-readable expiration times (e.g., "Expired 2h 30m ago")
- Handles edge cases like missing or invalid deadlines

### Workspace Categories Priority
1. **TTL Expired** - Highest priority (can be force-stopped anytime)
2. **Quiet Hours Stopping** - Active quiet hours with grace period over
3. **Quiet Hours Grace** - Active quiet hours within grace period
4. **Past Quiet Hours End** - Running beyond configured end time
5. **Normal Running** - Standard operation
6. **Excluded** - Protected from automatic stopping

## 📋 **Command Reference**

| Command | Description |
|---------|-------------|
| `--categorize` | Show detailed workspace categorization |
| `--execute` | Execute quiet hours stopping |
| `--execute --force` | Execute with TTL-expired workspace stopping |
| `--execute --dry-run` | Test execution without actually stopping |
| `--execute --force --dry-run` | Test force execution safely |
| `--status` | Show agent status with enterprise info |
| `--enterprise` | Show only enterprise configuration |

## 🔄 **Integration with Existing Features**

The enhanced features work seamlessly with existing functionality:

- **Enterprise Quiet Hours** - Still displayed in status output
- **Configuration** - All existing config options respected
- **Exclusions** - User and template exclusions still apply
- **Timezone Support** - All time calculations use configured timezone
- **Dry Run Mode** - Works with all new features
- **Logging** - Enhanced with detailed stop reasons

This enhancement provides comprehensive workspace lifecycle management while maintaining backward compatibility with existing quiet hours functionality.