# Enhanced Filtering for Prune Workspaces Agent

## 🎯 **Overview**

The Prune Workspaces Agent now supports comprehensive filtering based on **Organizations**, **Groups**, **Users**, and **Templates**. This allows for precise control over which workspaces are included or excluded from quiet hours management.

## 🔧 **Filtering Capabilities**

### **Filter Types**

| Filter Type | Include Option | Exclude Option | Description |
|-------------|----------------|----------------|-------------|
| **Organizations** | `--include-org` | `--exclude-org` | Filter by organization membership |
| **Groups** | `--include-group` | `--exclude-group` | Filter by group membership |
| **Users** | `--include-user` | `--exclude-user` | Filter by specific users |
| **Templates** | `--include-template` | `--exclude-template` | Filter by workspace templates |

### **Filter Logic**

1. **Include Filters**: If specified, only items matching these criteria are included
2. **Exclude Filters**: Items matching these criteria are excluded (takes precedence over include)
3. **Empty Filters**: If no include filters are specified, all items are included by default
4. **Multiple Values**: Each filter option can be used multiple times

## 🚀 **Usage Examples**

### **Organization-Based Filtering**

```bash
# Only include workspaces from "engineering" organization
python agents/prune_workspaces.py --include-org "engineering"

# Include multiple organizations
python agents/prune_workspaces.py --include-org "engineering" --include-org "qa"

# Exclude specific organizations
python agents/prune_workspaces.py --exclude-org "production" --exclude-org "critical-ops"

# Combine include and exclude (exclude takes precedence)
python agents/prune_workspaces.py --include-org "engineering" --exclude-org "production"
```

### **Group-Based Filtering**

```bash
# Only include workspaces from "developers" group
python agents/prune_workspaces.py --include-group "developers"

# Include multiple groups
python agents/prune_workspaces.py --include-group "developers" --include-group "testers"

# Exclude specific groups
python agents/prune_workspaces.py --exclude-group "on-call" --exclude-group "admins"

# Target all users but exclude admin groups
python agents/prune_workspaces.py --all --exclude-group "administrators"
```

### **User-Based Filtering**

```bash
# Only include specific users
python agents/prune_workspaces.py --include-user "john.doe" --include-user "jane.smith"

# Exclude specific users (in addition to config exclusions)
python agents/prune_workspaces.py --exclude-user "admin" --exclude-user "service-account"

# Include all users except specific ones
python agents/prune_workspaces.py --all --exclude-user "critical-user"
```

### **Template-Based Filtering**

```bash
# Only include workspaces from development templates
python agents/prune_workspaces.py --include-template "python-dev" --include-template "nodejs-dev"

# Exclude production templates
python agents/prune_workspaces.py --exclude-template "production-api" --exclude-template "critical-service"

# Include all templates except specific ones
python agents/prune_workspaces.py --all --exclude-template "production-template"
```

### **Combined Filtering**

```bash
# Complex filtering: Engineering org, developers group, exclude admin users, only dev templates
python agents/prune_workspaces.py \\
  --include-org "engineering" \\
  --include-group "developers" \\
  --exclude-user "admin" \\
  --include-template "python-dev" \\
  --include-template "nodejs-dev" \\
  --cleanup --dry-run

# Exclude multiple criteria
python agents/prune_workspaces.py \\
  --exclude-org "production" \\
  --exclude-group "on-call" \\
  --exclude-template "critical-service" \\
  --all --cleanup
```

## ⚙️ **Configuration File Support**

### **agents_config.json**

```json
{
  "prune_workspaces": {
    "enabled": true,
    "default_quiet_hours_duration": 8,
    "timezone": "UTC",
    "include_organizations": ["engineering", "qa"],
    "exclude_organizations": ["production"],
    "include_groups": ["developers", "testers"],
    "exclude_groups": ["on-call", "administrators"],
    "include_users": [],
    "exclude_users": ["admin", "service-account"],
    "include_templates": ["python-dev", "nodejs-dev"],
    "exclude_templates": ["production-api", "critical-service"]
  }
}
```

### **Configuration Priority**

1. **Command Line Arguments**: Override config file settings
2. **Config File**: Default filtering rules
3. **Built-in Defaults**: Fallback if no config specified

## 🔍 **Filter Resolution Process**

### **Step-by-Step Filtering**

1. **Get All Workspaces**: Fetch complete workspace list
2. **Apply Organization Filters**: Filter by user's organization membership
3. **Apply Group Filters**: Filter by user's group membership  
4. **Apply User Filters**: Filter by specific usernames
5. **Apply Template Filters**: Filter by workspace template IDs
6. **Apply Quiet Hours Logic**: Check if remaining workspaces are in quiet hours
7. **Return Results**: Final filtered list

### **Filter Interaction**

```
All Workspaces
    ↓
Organization Filter (include/exclude)
    ↓
Group Filter (include/exclude)
    ↓
User Filter (include/exclude)
    ↓
Template Filter (include/exclude)
    ↓
Quiet Hours Check
    ↓
Final Results
```

## 📊 **Real-World Scenarios**

### **Scenario 1: Development Team Cleanup**

**Goal**: Clean up workspaces for development teams during their quiet hours

```bash
python agents/prune_workspaces.py \\
  --include-org "engineering" \\
  --include-group "frontend-team" \\
  --include-group "backend-team" \\
  --exclude-template "production-api" \\
  --cleanup --duration 10
```

### **Scenario 2: Multi-Organization Management**

**Goal**: Manage workspaces across multiple organizations, excluding critical ones

```bash
python agents/prune_workspaces.py \\
  --include-org "engineering" \\
  --include-org "qa" \\
  --include-org "design" \\
  --exclude-org "production" \\
  --exclude-org "security" \\
  --all --cleanup --dry-run
```

### **Scenario 3: Template-Specific Cleanup**

**Goal**: Only manage development and testing templates

```bash
python agents/prune_workspaces.py \\
  --include-template "python-dev" \\
  --include-template "nodejs-dev" \\
  --include-template "react-dev" \\
  --include-template "test-env" \\
  --exclude-user "admin" \\
  --all --cleanup
```

### **Scenario 4: Emergency Exclusions**

**Goal**: Quickly exclude critical users and templates during incidents

```bash
python agents/prune_workspaces.py \\
  --exclude-user "incident-commander" \\
  --exclude-user "on-call-engineer" \\
  --exclude-template "incident-response" \\
  --exclude-group "emergency-response" \\
  --all --cleanup --dry-run
```

## 🛡️ **Safety Features**

### **Validation**

- **User Existence**: Validates that specified users exist
- **Organization Membership**: Checks actual organization membership
- **Group Membership**: Verifies group membership through API
- **Template Existence**: Validates template IDs exist

### **Dry Run Mode**

```bash
# Always test complex filters first
python agents/prune_workspaces.py \\
  --include-org "engineering" \\
  --exclude-group "on-call" \\
  --cleanup --dry-run
```

### **Caching**

- **User Lookups**: Cached to avoid repeated API calls
- **Organization Data**: Cached per execution
- **Group Membership**: Cached to improve performance

## 🔧 **API Integration**

### **Required Endpoints**

| Endpoint | Purpose | Required For |
|----------|---------|--------------|
| `/api/v2/organizations` | List organizations | Organization filtering |
| `/api/v2/groups` | List groups | Group filtering |
| `/api/v2/users` | List users | User validation |
| `/api/v2/groups/{id}/members` | Group membership | Group filtering |
| `/api/v2/users/{id}` | User details | Organization membership |

### **Permissions Required**

- **Read Organizations**: To list and filter by organizations
- **Read Groups**: To list groups and check membership
- **Read Users**: To validate users and get organization membership
- **Read Workspaces**: To list and analyze workspaces

## 📈 **Performance Considerations**

### **Optimization Strategies**

1. **Caching**: User, organization, and group data cached per execution
2. **Batch Processing**: Efficient API usage for large datasets
3. **Early Filtering**: Apply filters in order of selectivity
4. **Lazy Loading**: Only fetch additional data when needed

### **Large Environment Tips**

```bash
# For large environments, use specific filters to reduce API calls
python agents/prune_workspaces.py \\
  --include-org "specific-org" \\
  --include-group "specific-group" \\
  --cleanup

# Avoid broad filters in very large environments
# Instead of --all, use specific organization/group targeting
```

## 🚨 **Troubleshooting**

### **Common Issues**

1. **No Workspaces Found**
   - Check filter criteria are correct
   - Verify organization/group names match exactly
   - Use `--json` to see detailed filter results

2. **Permission Errors**
   - Ensure API token has required permissions
   - Check organization/group access rights
   - Verify user can read organization and group data

3. **Performance Issues**
   - Use more specific filters to reduce API calls
   - Avoid `--all` with broad include filters
   - Consider running during off-peak hours

### **Debug Commands**

```bash
# Check what organizations are available
python agents/workspace_controller.py  # Will show basic info

# Test filters with JSON output
python agents/prune_workspaces.py --include-org "engineering" --json

# Dry run with verbose filtering
python agents/prune_workspaces.py --all --dry-run --json
```

## 🎯 **Best Practices**

### **Filter Design**

1. **Start Specific**: Begin with narrow filters and expand as needed
2. **Test First**: Always use `--dry-run` with new filter combinations
3. **Document Filters**: Keep track of filter combinations that work well
4. **Regular Review**: Periodically review and update filter criteria

### **Production Usage**

```bash
# Production-safe approach
python agents/prune_workspaces.py \\
  --include-org "development" \\
  --exclude-group "on-call" \\
  --exclude-template "production-api" \\
  --cleanup --dry-run

# If dry run looks good, remove --dry-run
python agents/prune_workspaces.py \\
  --include-org "development" \\
  --exclude-group "on-call" \\
  --exclude-template "production-api" \\
  --cleanup
```

This enhanced filtering system provides granular control over workspace management while maintaining safety and performance in enterprise environments.