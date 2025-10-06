# Coder Workspace Management Agents - Example Output

This document shows example outputs from the various workspace management agents to help users understand what to expect when running the tools.

## 📋 **Table of Contents**

- [Example Usage Script](#example-usage-script)
- [Prune Workspaces Agent - Dry Run](#prune-workspaces-agent---dry-run)
- [Prune Workspaces Agent - Live Execution](#prune-workspaces-agent---live-execution)

---

## 🚀 **Example Usage Script**

The `example_usage.py` script demonstrates all major agent functionality:

```bash
$ python example_usage.py
```

### **Output:**

```
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
```

---

## 🧪 **Prune Workspaces Agent - Dry Run**

Testing the prune workspaces functionality with dry-run mode:

```bash
$ python prune_workspaces.py --cleanup --dry-run
```

### **Output:**

```
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
aqua-eagle-61             Envbuilder-JB-NotWorking       stopped   2025-06-04
Bundler                   kubernetesKasm-Bundle          stopped   2025-08-26
CertTwo                   devcontainer-kubernetes-cert   stopped   2025-01-24
coffee-whitefish-74       Dynamics                       stopped   2025-09-11
CoPiloting2               VSCode-NodeJS                  stopped   2025-08-21
Cursor                    VSCode-Cursor                  stopped   2025-03-25
cyan-dragonfly-35         BrokenArray                    stopped   2025-08-27
Devcontainer              devcontainer-kubernetes        stopped   2025-01-22
EnvboxFedora              Envbox-Fedora                  stopped   2025-03-06
ExecTrace                 EnvExectrace                   stopped   2025-07-02
fuchsia-parrot-51         yelp                           stopped   2025-05-28
GH-Copilot                VSCode-Native                  stopped   2025-07-17
GitHub                    kubernetes-git                 stopped   2025-06-30
gray-camel-31             kubernetes                     stopped   2025-06-27
HTX                       AirGapped                      stopped   2025-06-25
indigo-gecko-44           devcontainer-kubernetes        stopped   2025-06-23
indigo-hamster-60         VSCode-Jupyter-GPU-systemd     stopped   2025-06-23
JetBrain1                 kubernetes                     stopped   2025-01-30
JupyterGPU                JupyterLab-GPU                 stopped   2025-02-10
JupyterLab                JupyterLab                     stopped   2025-02-07
KasmFedora                kubernetesKasm-fedora          stopped   2025-07-17
KasmVNC                   kubernetesKasm                 stopped   2025-03-05
KasmVNC-GAP               gap-kasm                       stopped   2025-03-07
KasmVNC-Jammy             gap-kasm                       stopped   2025-05-23
KubernetesOne             kubernetes                     stopped   2025-01-22
moccasin-moose-74         kubernetes-mounted-vars        stopped   2025-06-13
NativeVSCode              VSCode-Native                  stopped   2025-06-25
OnStop                    kubernetes-git                 stopped   2025-07-03
peach-swift-78            kubernetes-configmap           stopped   2025-06-13
plum-hawk-44              Envbox                         stopped   2025-06-20
PNGx2                     VSCode-Jupyter-GPU-systemd     stopped   2025-07-09
PodmanFive                kubernetes-podman              stopped   2025-03-17
PortSharing               kubernetes                     stopped   2025-05-20
red-asp-6                 kubernetes-params              stopped   2025-06-13
red-fly-94                Envbuilder-JB-NotWorking       stopped   2025-06-20
renamed                   VSCode-Jupyter-GPU             stopped   2025-02-20
RhelKasm                  kubernetesKasm-fedora          stopped   2025-07-17
rose-tarsier-47           kubernetes-Terraform-VNC       stopped   2025-05-07
sapphire-quokka-45        Envbuilder-JB-Cert-Envbuilder  stopped   2025-06-24
serve-web                 VSCode-Native                  stopped   2025-08-27
teal-parrot-60            webstorm-ubuntu-template       stopped   2025-09-03
test-disabled-ws          test                           stopped   2025-09-18
test-dynamic-ws2          test                           stopped   2025-09-18
test-on-stop-improved-v2  test-on-stop-improved          stopped   2025-08-21
test-ws                   test                           stopped   2025-09-18
VSCode-Or-What            VSCode-Jupyter-GPU             stopped   2025-02-14
webstorm-ubuntu-demo      webstorm-ubuntu-template       stopped   2025-09-03
WithModuleLogin           kubernetes-Terraform-Max       stopped   2025-04-17
withshm                   Envbox-SHM                     stopped   2025-05-21
WithSystemD               VSCode-Jupyter-GPU-systemd     stopped   2025-07-09


🧪 [DRY RUN] Cleaning up 1 running workspaces:
------------------------------------------------------------
  🧪 [DRY RUN] Would stop: $USER/$WORKSPACE ($TEMPLATE) - running
     Owner: $USER
     Reason: Pruned during quiet hours

📊 Cleanup completed: 1/1 workspaces processed successfully
```

### **Key Observations:**

- **52 workspaces** found within quiet hours period
- **51 already stopped**, only **1 running**
- **Dry-run mode** shows what would happen without making changes
- **Safe testing** allows verification before actual execution

---

## 🛑 **Prune Workspaces Agent - Live Execution**

Actual workspace stopping during quiet hours:

```bash
$ python prune_workspaces.py --cleanup
```

### **Output:**

```
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
aqua-eagle-61             Envbuilder-JB-NotWorking       stopped   2025-06-04
Bundler                   kubernetesKasm-Bundle          stopped   2025-08-26
CertTwo                   devcontainer-kubernetes-cert   stopped   2025-01-24
coffee-whitefish-74       Dynamics                       stopped   2025-09-11
CoPiloting2               VSCode-NodeJS                  stopped   2025-08-21
Cursor                    VSCode-Cursor                  stopped   2025-03-25
cyan-dragonfly-35         BrokenArray                    stopped   2025-08-27
Devcontainer              devcontainer-kubernetes        stopped   2025-01-22
EnvboxFedora              Envbox-Fedora                  stopped   2025-03-06
ExecTrace                 EnvExectrace                   stopped   2025-07-02
fuchsia-parrot-51         yelp                           stopped   2025-05-28
GH-Copilot                VSCode-Native                  stopped   2025-07-17
GitHub                    kubernetes-git                 stopped   2025-06-30
gray-camel-31             kubernetes                     stopped   2025-06-27
HTX                       AirGapped                      stopped   2025-06-25
indigo-gecko-44           devcontainer-kubernetes        stopped   2025-06-23
indigo-hamster-60         VSCode-Jupyter-GPU-systemd     stopped   2025-06-23
JetBrain1                 kubernetes                     stopped   2025-01-30
JupyterGPU                JupyterLab-GPU                 stopped   2025-02-10
JupyterLab                JupyterLab                     stopped   2025-02-07
KasmFedora                kubernetesKasm-fedora          stopped   2025-07-17
KasmVNC                   kubernetesKasm                 stopped   2025-03-05
KasmVNC-GAP               gap-kasm                       stopped   2025-03-07
KasmVNC-Jammy             gap-kasm                       stopped   2025-05-23
KubernetesOne             kubernetes                     stopped   2025-01-22
moccasin-moose-74         kubernetes-mounted-vars        stopped   2025-06-13
NativeVSCode              VSCode-Native                  stopped   2025-06-25
OnStop                    kubernetes-git                 stopped   2025-07-03
peach-swift-78            kubernetes-configmap           stopped   2025-06-13
plum-hawk-44              Envbox                         stopped   2025-06-20
PNGx2                     VSCode-Jupyter-GPU-systemd     stopped   2025-07-09
PodmanFive                kubernetes-podman              stopped   2025-03-17
PortSharing               kubernetes                     stopped   2025-05-20
red-asp-6                 kubernetes-params              stopped   2025-06-13
red-fly-94                Envbuilder-JB-NotWorking       stopped   2025-06-20
renamed                   VSCode-Jupyter-GPU             stopped   2025-02-20
RhelKasm                  kubernetesKasm-fedora          stopped   2025-07-17
rose-tarsier-47           kubernetes-Terraform-VNC       stopped   2025-05-07
sapphire-quokka-45        Envbuilder-JB-Cert-Envbuilder  stopped   2025-06-24
serve-web                 VSCode-Native                  stopped   2025-08-27
teal-parrot-60            webstorm-ubuntu-template       stopped   2025-09-03
test-disabled-ws          test                           stopped   2025-09-18
test-dynamic-ws2          test                           stopped   2025-09-18
test-on-stop-improved-v2  test-on-stop-improved          stopped   2025-08-21
test-ws                   test                           stopped   2025-09-18
VSCode-Or-What            VSCode-Jupyter-GPU             stopped   2025-02-14
webstorm-ubuntu-demo      webstorm-ubuntu-template       stopped   2025-09-03
WithModuleLogin           kubernetes-Terraform-Max       stopped   2025-04-17
withshm                   Envbox-SHM                     stopped   2025-05-21
WithSystemD               VSCode-Jupyter-GPU-systemd     stopped   2025-07-09


🛑 Cleaning up 1 running workspaces:
------------------------------------------------------------
  🛑 Stopping: $USER/$WORKSPACE ($TEMPLATE) - running
     Owner: $USER
     Reason: Pruned during quiet hours
Successfully initiated stop for workspace 284d08ed-31ce-4b93-b482-9de727f7f731: Pruned during quiet hours
     Result: ✅ Success

📊 Cleanup completed: 1/1 workspaces processed successfully
```

### **Key Observations:**

- **Actual workspace stopping** performed successfully
- **API call successful** with workspace ID confirmation
- **Clear success reporting** shows operation completed
- **Detailed logging** provides audit trail for stopped workspaces

---

## 💡 **Usage Tips**

### **Testing Workflow:**
1. **Always start with dry-run** to see what would happen
2. **Review the output** to ensure expected behavior
3. **Run live execution** only after confirming dry-run results
4. **Monitor logs** for any errors or unexpected behavior

### **Common Patterns:**
- **Most workspaces stopped**: Normal in quiet hours periods
- **Few running workspaces**: Expected during off-hours
- **Success rate tracking**: Helps identify API or permission issues
- **Detailed workspace lists**: Useful for auditing and compliance

### **Troubleshooting:**
- If no workspaces found, check quiet hours configuration
- If API errors occur, verify CODER_URL and CODER_TOKEN
- If permissions denied, ensure token has workspace management rights
- If unexpected results, review user's enterprise quiet hours settings