#!/bin/bash
# Installation script for Coder Workspace Management Agents
# Extends the coder-audit-simple project

set -e

echo "🚀 Installing Coder Workspace Management Agents"
echo "================================================"

# Check Python version
echo "📋 Checking Python version..."
python3 --version || {
    echo "❌ Python 3 is required but not installed"
    exit 1
}

# Check if we're in the right directory
if [ ! -f "AGENTS.md" ]; then
    echo "❌ Please run this script from the project root directory"
    exit 1
fi

# Install Python dependencies
echo "📦 Installing Python dependencies..."
if [ -f "requirements.txt" ]; then
    pip3 install -r requirements.txt
else
    echo "⚠️  requirements.txt not found, installing basic dependencies..."
    pip3 install requests tabulate pytz
fi

# Make scripts executable
echo "🔧 Making scripts executable..."
chmod +x agents/*.py

# Check for configuration
echo "⚙️  Checking configuration..."
if [ ! -f "agents_config.json" ]; then
    echo "⚠️  agents_config.json not found, using default configuration"
else
    echo "✅ Configuration file found"
fi

# Check environment variables
echo "🔍 Checking environment variables..."
if [ -z "$CODER_URL" ]; then
    echo "⚠️  CODER_URL environment variable not set"
    echo "   Please set it with: export CODER_URL='https://your-coder-instance.com'"
fi

if [ -z "$CODER_TOKEN" ] && [ ! -f "audit-token.txt" ]; then
    echo "⚠️  CODER_TOKEN environment variable not set and audit-token.txt not found"
    echo "   Please set one of:"
    echo "   - export CODER_TOKEN='your-api-token'"
    echo "   - echo 'your-api-token' > audit-token.txt"
fi

# Test connection (if credentials are available)
echo "🔌 Testing connection to Coder API..."
if [ -n "$CODER_URL" ] && ([ -n "$CODER_TOKEN" ] || [ -f "audit-token.txt" ]); then
    cd agents
    if python3 workspace_controller.py > /dev/null 2>&1; then
        echo "✅ Successfully connected to Coder API"
    else
        echo "❌ Failed to connect to Coder API"
        echo "   Please check your CODER_URL and CODER_TOKEN"
    fi
    cd ..
else
    echo "⏭️  Skipping connection test (credentials not configured)"
fi

# Create systemd service file (optional)
echo "🔧 Creating systemd service template..."
cat > coder-agents.service << 'EOF'
[Unit]
Description=Coder Workspace Management Agents
After=network.target

[Service]
Type=simple
User=coder-agent
WorkingDirectory=/opt/coder-agents
Environment=CODER_URL=https://your-coder-instance.com
Environment=CODER_TOKEN=your-api-token
ExecStart=/usr/bin/python3 -m agents.quiet_hours_agent --execute
Restart=always
RestartSec=300

[Install]
WantedBy=multi-user.target
EOF

echo "📝 Created coder-agents.service template"
echo "   Edit the file and copy to /etc/systemd/system/ to enable as a service"

# Create cron job examples
echo "⏰ Creating cron job examples..."
cat > cron-examples.txt << 'EOF'
# Coder Workspace Management Agents - Cron Job Examples
# Add these to your crontab with: crontab -e

# Check quiet hours every 15 minutes
*/15 * * * * cd /path/to/coder-agents && python3 agents/quiet_hours_agent.py --execute >> /var/log/coder-agents.log 2>&1

# Generate TTL compliance report every hour
0 * * * * cd /path/to/coder-agents && python3 agents/ttl_monitor_agent.py --report >> /var/log/coder-ttl-reports.log 2>&1

# Monitor TTL compliance continuously (alternative to hourly reports)
# @reboot cd /path/to/coder-agents && python3 agents/ttl_monitor_agent.py --monitor >> /var/log/coder-ttl-monitor.log 2>&1
EOF

echo "📝 Created cron-examples.txt with scheduling examples"

# Run example usage (if credentials are available)
echo "🧪 Running example usage..."
if [ -n "$CODER_URL" ] && ([ -n "$CODER_TOKEN" ] || [ -f "audit-token.txt" ]); then
    cd agents
    echo "   This will demonstrate the agents functionality..."
    python3 example_usage.py
    cd ..
else
    echo "⏭️  Skipping example usage (credentials not configured)"
fi

echo ""
echo "✅ Installation completed!"
echo ""
echo "📚 Next steps:"
echo "1. Set environment variables:"
echo "   export CODER_URL='https://your-coder-instance.com'"
echo "   export CODER_TOKEN='your-api-token'"
echo ""
echo "2. Test the agents:"
echo "   python3 agents/quiet_hours_agent.py --status"
echo "   python3 agents/ttl_monitor_agent.py --report"
echo ""
echo "3. Configure scheduling (see cron-examples.txt)"
echo ""
echo "4. Customize configuration in agents_config.json"
echo ""
echo "📖 For detailed documentation, see AGENTS.md"