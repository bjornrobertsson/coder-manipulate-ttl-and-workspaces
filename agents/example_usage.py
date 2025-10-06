#!/usr/bin/env python3
"""
Example Usage - Demonstrates how to use the Coder Workspace Management Agents
This script shows practical examples of using the agents programmatically
"""

import sys
import json
from datetime import datetime

# Import the agents
from workspace_controller import WorkspaceController
from quiet_hours_agent import QuietHoursAgent
from ttl_monitor_agent import TTLMonitorAgent

def example_basic_workspace_operations():
    """Example: Basic workspace operations using WorkspaceController"""
    print("=" * 60)
    print("EXAMPLE 1: Basic Workspace Operations")
    print("=" * 60)
    
    try:
        # Initialize controller
        controller = WorkspaceController()
        
        # Test connection
        if not controller.validate_connection():
            print("❌ Failed to connect to Coder API")
            return False
        
        print("✅ Connected to Coder API successfully")
        
        # Get all workspaces
        all_workspaces = controller.get_workspaces()
        print(f"📊 Total workspaces: {len(all_workspaces)}")
        
        # Get running workspaces
        running = controller.get_running_workspaces()
        print(f"🟢 Running workspaces: {len(running)}")
        
        # Show running workspaces
        if running:
            print("\nRunning workspaces:")
            for ws in running[:5]:  # Show first 5
                print(f"  - {controller.workspace_summary(ws)}")
            if len(running) > 5:
                print(f"  ... and {len(running) - 5} more")
        
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def example_quiet_hours_check():
    """Example: Check quiet hours status"""
    print("\n" + "=" * 60)
    print("EXAMPLE 2: Quiet Hours Status Check")
    print("=" * 60)
    
    try:
        # Initialize quiet hours agent
        agent = QuietHoursAgent()
        
        # Check current status
        current_time = agent._get_current_time()
        is_quiet = agent.is_quiet_hours()
        grace_over = agent.is_grace_period_over()
        
        print(f"🕐 Current time: {current_time.strftime('%Y-%m-%d %H:%M:%S %Z')}")
        print(f"🌙 Quiet hours active: {'Yes' if is_quiet else 'No'}")
        print(f"⏰ Grace period over: {'Yes' if grace_over else 'No'}")
        
        # Get workspaces that would be affected
        workspaces_to_stop = agent.get_workspaces_to_stop()
        print(f"🛑 Workspaces to stop: {len(workspaces_to_stop)}")
        
        if workspaces_to_stop:
            print("\nWorkspaces that would be stopped:")
            for ws in workspaces_to_stop[:3]:  # Show first 3
                print(f"  - {agent.controller.workspace_summary(ws)}")
            if len(workspaces_to_stop) > 3:
                print(f"  ... and {len(workspaces_to_stop) - 3} more")
        
        # Generate and show report
        print("\n📋 Generating detailed report...")
        report = agent.generate_report()
        print(f"Action required: {report['action_required']}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def example_ttl_compliance():
    """Example: TTL compliance monitoring"""
    print("\n" + "=" * 60)
    print("EXAMPLE 3: TTL Compliance Report")
    print("=" * 60)
    
    try:
        # Initialize TTL monitor agent
        agent = TTLMonitorAgent()
        
        # Generate compliance report
        report = agent.get_ttl_compliance_report()
        
        print(f"📊 Total workspaces analyzed: {report['total_workspaces']}")
        print(f"🔴 Expired: {report['summary']['expired']}")
        print(f"🟡 Expiring soon: {report['summary']['expiring_soon']}")
        print(f"🟢 Running normally: {report['summary']['running']}")
        print(f"⚫ Stopped: {report['summary']['stopped']}")
        
        # Show expired workspaces
        if report['workspaces']['expired']:
            print("\n🔴 Workspaces that SHOULD HAVE STOPPED:")
            for ws in report['workspaces']['expired'][:3]:
                print(f"  - {ws['owner']}/{ws['name']}: {ws['time_remaining']}")
            if len(report['workspaces']['expired']) > 3:
                print(f"  ... and {len(report['workspaces']['expired']) - 3} more")
        
        # Show expiring soon
        if report['workspaces']['expiring_soon']:
            print("\n🟡 Workspaces EXPIRING SOON:")
            for ws in report['workspaces']['expiring_soon'][:3]:
                print(f"  - {ws['owner']}/{ws['name']}: {ws['time_remaining']}")
            if len(report['workspaces']['expiring_soon']) > 3:
                print(f"  ... and {len(report['workspaces']['expiring_soon']) - 3} more")
        
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def example_combined_analysis():
    """Example: Combined analysis using multiple agents"""
    print("\n" + "=" * 60)
    print("EXAMPLE 4: Comprehensive Workspace Analysis")
    print("=" * 60)
    
    try:
        # Initialize agents
        controller = WorkspaceController()
        quiet_agent = QuietHoursAgent()
        ttl_agent = TTLMonitorAgent()
        
        print("🔍 Performing combined workspace analysis...")
        
        # Get all running workspaces
        running_workspaces = controller.get_running_workspaces()
        
        # Analyze each workspace
        analysis_results = {
            "total_running": len(running_workspaces),
            "quiet_hours_affected": 0,
            "ttl_expired": 0,
            "ttl_expiring_soon": 0,
            "action_needed": []
        }
        
        # Check quiet hours impact
        if quiet_agent.is_quiet_hours() and quiet_agent.is_grace_period_over():
            quiet_workspaces = quiet_agent.get_workspaces_to_stop()
            analysis_results["quiet_hours_affected"] = len(quiet_workspaces)
            
            for ws in quiet_workspaces:
                analysis_results["action_needed"].append({
                    "workspace": controller.workspace_summary(ws),
                    "reason": "Quiet hours policy",
                    "priority": "high"
                })
        
        # Check TTL compliance
        ttl_report = ttl_agent.get_ttl_compliance_report()
        analysis_results["ttl_expired"] = ttl_report["summary"]["expired"]
        analysis_results["ttl_expiring_soon"] = ttl_report["summary"]["expiring_soon"]
        
        for ws in ttl_report["workspaces"]["expired"]:
            analysis_results["action_needed"].append({
                "workspace": f"{ws['owner']}/{ws['name']}",
                "reason": f"TTL expired: {ws['time_remaining']}",
                "priority": "critical"
            })
        
        # Display results
        print(f"📊 Analysis Results:")
        print(f"  Total running workspaces: {analysis_results['total_running']}")
        print(f"  Affected by quiet hours: {analysis_results['quiet_hours_affected']}")
        print(f"  TTL expired: {analysis_results['ttl_expired']}")
        print(f"  TTL expiring soon: {analysis_results['ttl_expiring_soon']}")
        
        if analysis_results["action_needed"]:
            print(f"\n⚠️  Actions needed ({len(analysis_results['action_needed'])}):")
            for action in analysis_results["action_needed"][:5]:
                priority_icon = "🔥" if action["priority"] == "critical" else "⚡"
                print(f"  {priority_icon} {action['workspace']}: {action['reason']}")
            
            if len(analysis_results["action_needed"]) > 5:
                print(f"  ... and {len(analysis_results['action_needed']) - 5} more")
        else:
            print("\n✅ No immediate actions needed")
        
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def example_dry_run_operations():
    """Example: Demonstrate dry-run operations"""
    print("\n" + "=" * 60)
    print("EXAMPLE 5: Dry-Run Workspace Management")
    print("=" * 60)
    
    try:
        # Initialize quiet hours agent with dry-run enabled
        quiet_agent = QuietHoursAgent()
        quiet_agent.dry_run = True
        
        print("🧪 Running in DRY-RUN mode (no actual changes will be made)")
        
        # Simulate quiet hours stopping
        print("\n🌙 Simulating quiet hours workspace stopping...")
        results = quiet_agent.stop_workspaces_for_quiet_hours()
        
        if results:
            print(f"✅ Dry-run completed: {len(results)} workspaces would be affected")
            success_count = sum(1 for success in results.values() if success)
            print(f"📊 Success rate: {success_count}/{len(results)}")
        else:
            print("ℹ️  No workspaces would be affected by quiet hours policy")
        
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def main():
    """Run all examples"""
    print("🚀 Coder Workspace Management Agents - Example Usage")
    print("=" * 80)
    
    examples = [
        ("Basic Workspace Operations", example_basic_workspace_operations),
        ("Quiet Hours Status Check", example_quiet_hours_check),
        ("TTL Compliance Monitoring", example_ttl_compliance),
        ("Combined Analysis", example_combined_analysis),
        ("Dry-Run Operations", example_dry_run_operations)
    ]
    
    results = []
    
    for name, example_func in examples:
        try:
            success = example_func()
            results.append((name, success))
        except Exception as e:
            print(f"❌ Example '{name}' failed: {e}")
            results.append((name, False))
    
    # Summary
    print("\n" + "=" * 80)
    print("EXAMPLE EXECUTION SUMMARY")
    print("=" * 80)
    
    for name, success in results:
        status = "✅ PASSED" if success else "❌ FAILED"
        print(f"{status}: {name}")
    
    successful = sum(1 for _, success in results if success)
    print(f"\n📊 Overall: {successful}/{len(results)} examples completed successfully")
    
    if successful < len(results):
        print("\n💡 Tips for troubleshooting:")
        print("  • Check CODER_URL and CODER_TOKEN environment variables")
        print("  • Ensure API token has workspace management permissions")
        print("  • Verify network connectivity to Coder instance")
        print("  • Check agents_config.json for valid configuration")

if __name__ == "__main__":
    main()