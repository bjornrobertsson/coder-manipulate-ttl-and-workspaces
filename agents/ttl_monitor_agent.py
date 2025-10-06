#!/usr/bin/env python3
"""
TTL Monitor Agent - Monitor workspace TTL settings and display compliance status
Extends the coder-audit-simple project with TTL monitoring and prediction
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Optional, Tuple
from tabulate import tabulate

# Import the workspace controller
from workspace_controller import WorkspaceController

class TTLMonitorAgent:
    """Agent for monitoring workspace TTL compliance and predictions"""
    
    def __init__(self, config_file: str = "agents_config.json"):
        """
        Initialize TTL monitor agent
        
        Args:
            config_file: Path to configuration file
        """
        self.config = self._load_config(config_file)
        self.controller = WorkspaceController()
        
    def _load_config(self, config_file: str) -> Dict:
        """Load configuration from file or use defaults"""
        default_config = {
            "ttl_monitor": {
                "enabled": True,
                "warning_threshold_hours": 1,
                "check_interval_minutes": 15,
                "report_expired": True,
                "report_expiring_soon": True
            }
        }
        
        if os.path.exists(config_file):
            try:
                with open(config_file, 'r') as f:
                    file_config = json.load(f)
                    default_config.update(file_config)
            except Exception as e:
                print(f"Warning: Could not load config file {config_file}: {e}")
        
        return default_config
    
    def _format_time_remaining(self, deadline_str: str) -> Tuple[str, int, bool]:
        """
        Format time remaining until deadline
        
        Args:
            deadline_str: ISO format deadline string
            
        Returns:
            Tuple of (formatted_string, seconds_remaining, is_expired)
        """
        if not deadline_str or deadline_str == "N/A":
            return "N/A", 0, False
        
        try:
            deadline = datetime.fromisoformat(deadline_str.replace('Z', '+00:00'))
            now = datetime.now(timezone.utc)
            remaining = deadline - now
            seconds_remaining = int(remaining.total_seconds())
            
            if seconds_remaining < 0:
                # Expired
                abs_seconds = abs(seconds_remaining)
                if abs_seconds < 3600:
                    return f"Expired {abs_seconds // 60}m ago", seconds_remaining, True
                elif abs_seconds < 86400:
                    hours = abs_seconds // 3600
                    minutes = (abs_seconds % 3600) // 60
                    return f"Expired {hours}h {minutes}m ago", seconds_remaining, True
                else:
                    days = abs_seconds // 86400
                    hours = (abs_seconds % 86400) // 3600
                    return f"Expired {days}d {hours}h ago", seconds_remaining, True
            else:
                # Not expired
                if seconds_remaining < 3600:
                    return f"{seconds_remaining // 60}m", seconds_remaining, False
                elif seconds_remaining < 86400:
                    hours = seconds_remaining // 3600
                    minutes = (seconds_remaining % 3600) // 60
                    return f"{hours}h {minutes}m", seconds_remaining, False
                else:
                    days = seconds_remaining // 86400
                    hours = (seconds_remaining % 86400) // 3600
                    return f"{days}d {hours}h", seconds_remaining, False
                    
        except Exception as e:
            return f"Invalid: {e}", 0, False
    
    def _format_ttl(self, ttl_ms: int) -> str:
        """Format TTL from milliseconds to human-readable format"""
        if not ttl_ms:
            return "N/A"
        
        seconds = ttl_ms / 1000
        
        if seconds < 3600:
            return f"{int(seconds // 60)}m"
        elif seconds < 86400:
            return f"{int(seconds // 3600)}h"
        else:
            days = int(seconds // 86400)
            hours = int((seconds % 86400) // 3600)
            if hours > 0:
                return f"{days}d {hours}h"
            else:
                return f"{days}d"
    
    def _format_date(self, date_str: str) -> str:
        """Format date string to readable format"""
        if not date_str or date_str == "0001-01-01T00:00:00Z":
            return "N/A"
        try:
            dt = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
            return dt.strftime("%Y-%m-%d %H:%M:%S")
        except:
            return date_str
    
    def analyze_workspace_ttl(self, workspace: Dict) -> Dict:
        """
        Analyze TTL compliance for a single workspace
        
        Args:
            workspace: Workspace dictionary
            
        Returns:
            Analysis dictionary with TTL information
        """
        analysis = {
            "workspace_id": workspace.get('id'),
            "owner": workspace.get('owner_name'),
            "name": workspace.get('name'),
            "template_id": workspace.get('template_id'),
            "status": workspace.get('latest_build', {}).get('status'),
            "ttl_ms": workspace.get('ttl_ms'),
            "ttl_formatted": self._format_ttl(workspace.get('ttl_ms', 0)),
            "deadline": workspace.get('latest_build', {}).get('deadline'),
            "max_deadline": workspace.get('latest_build', {}).get('max_deadline'),
            "created_at": workspace.get('created_at'),
            "updated_at": workspace.get('updated_at')
        }
        
        # Analyze deadline
        deadline = analysis["deadline"]
        if deadline:
            time_remaining, seconds_remaining, is_expired = self._format_time_remaining(deadline)
            analysis.update({
                "time_remaining": time_remaining,
                "seconds_remaining": seconds_remaining,
                "is_expired": is_expired,
                "deadline_formatted": self._format_date(deadline)
            })
        else:
            analysis.update({
                "time_remaining": "N/A",
                "seconds_remaining": 0,
                "is_expired": False,
                "deadline_formatted": "N/A"
            })
        
        # Determine compliance status - only flag running workspaces as problematic
        warning_threshold = self.config["ttl_monitor"]["warning_threshold_hours"] * 3600
        
        # First check if workspace is running
        if analysis["status"] != "running":
            analysis["compliance_status"] = "STOPPED"
        elif analysis["is_expired"]:
            # Only running workspaces with expired TTL are problematic
            analysis["compliance_status"] = "EXPIRED"
        elif analysis["seconds_remaining"] > 0 and analysis["seconds_remaining"] <= warning_threshold:
            # Only running workspaces expiring soon are concerning
            analysis["compliance_status"] = "EXPIRING_SOON"
        else:
            # Running workspace with normal TTL
            analysis["compliance_status"] = "RUNNING"
        
        return analysis
    
    def get_ttl_compliance_report(self, user_filter: str = None) -> Dict:
        """
        Generate comprehensive TTL compliance report
        
        Args:
            user_filter: Optional username to filter by
            
        Returns:
            Compliance report dictionary
        """
        # Get all workspaces
        all_workspaces = self.controller.get_workspaces()
        
        # Filter by user if specified
        if user_filter:
            all_workspaces = [ws for ws in all_workspaces 
                            if ws.get('owner_name') == user_filter]
        
        # Analyze each workspace
        analyses = []
        for workspace in all_workspaces:
            analysis = self.analyze_workspace_ttl(workspace)
            analyses.append(analysis)
        
        # Categorize workspaces
        expired = [a for a in analyses if a["compliance_status"] == "EXPIRED"]
        expiring_soon = [a for a in analyses if a["compliance_status"] == "EXPIRING_SOON"]
        running = [a for a in analyses if a["compliance_status"] == "RUNNING"]
        stopped = [a for a in analyses if a["compliance_status"] == "STOPPED"]
        
        # Sort by time remaining (expired first, then by urgency)
        expired.sort(key=lambda x: x["seconds_remaining"])  # Most overdue first
        expiring_soon.sort(key=lambda x: x["seconds_remaining"])  # Soonest first
        
        report = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "total_workspaces": len(analyses),
            "user_filter": user_filter,
            "summary": {
                "expired": len(expired),
                "expiring_soon": len(expiring_soon),
                "running": len(running),
                "stopped": len(stopped)
            },
            "workspaces": {
                "expired": expired,
                "expiring_soon": expiring_soon,
                "running": running,
                "stopped": stopped
            }
        }
        
        return report
    
    def print_compliance_report(self, user_filter: str = None, 
                              show_all: bool = False):
        """
        Print formatted TTL compliance report
        
        Args:
            user_filter: Optional username to filter by
            show_all: Whether to show all workspaces or just problematic ones
        """
        report = self.get_ttl_compliance_report(user_filter)
        
        print("=" * 80)
        print("TTL COMPLIANCE REPORT")
        print("=" * 80)
        print(f"Generated: {self._format_date(report['timestamp'])}")
        if user_filter:
            print(f"User Filter: {user_filter}")
        print(f"Total Workspaces: {report['total_workspaces']}")
        print()
        
        # Summary
        summary = report['summary']
        print("SUMMARY:")
        print(f"  Expired: {summary['expired']}")
        print(f"  Expiring Soon: {summary['expiring_soon']}")
        print(f"  Running: {summary['running']}")
        print(f"  Stopped: {summary['stopped']}")
        print()
        
        # Expired workspaces
        if report['workspaces']['expired']:
            print("🔴 RUNNING WORKSPACES THAT SHOULD BE STOPPED (TTL EXPIRED):")
            print("-" * 80)
            
            table_data = []
            for ws in report['workspaces']['expired']:
                table_data.append([
                    ws['owner'],
                    ws['name'],
                    ws['ttl_formatted'],
                    ws['time_remaining'],
                    ws['deadline_formatted']
                ])
            
            headers = ["Owner", "Workspace", "TTL", "Status", "Deadline"]
            print(tabulate(table_data, headers=headers, tablefmt="grid"))
            print()
        
        # Expiring soon
        if report['workspaces']['expiring_soon']:
            print("🟡 RUNNING WORKSPACES EXPIRING SOON:")
            print("-" * 80)
            
            table_data = []
            for ws in report['workspaces']['expiring_soon']:
                table_data.append([
                    ws['owner'],
                    ws['name'],
                    ws['ttl_formatted'],
                    ws['time_remaining'],
                    ws['deadline_formatted']
                ])
            
            headers = ["Owner", "Workspace", "TTL", "Time Remaining", "Deadline"]
            print(tabulate(table_data, headers=headers, tablefmt="grid"))
            print()
        
        # Running workspaces (if requested)
        if show_all and report['workspaces']['running']:
            print("🟢 RUNNING WORKSPACES:")
            print("-" * 80)
            
            table_data = []
            for ws in report['workspaces']['running']:
                table_data.append([
                    ws['owner'],
                    ws['name'],
                    ws['ttl_formatted'],
                    ws['time_remaining'],
                    ws['status']
                ])
            
            headers = ["Owner", "Workspace", "TTL", "Time Remaining", "Status"]
            print(tabulate(table_data, headers=headers, tablefmt="simple"))
            print()
        
        # Recommendations
        print("RECOMMENDATIONS:")
        if summary['expired'] > 0:
            print(f"  • {summary['expired']} RUNNING workspace(s) have exceeded their TTL and should be stopped")
        if summary['expiring_soon'] > 0:
            threshold = self.config["ttl_monitor"]["warning_threshold_hours"]
            print(f"  • {summary['expiring_soon']} RUNNING workspace(s) will expire within {threshold} hour(s)")
        if summary['expired'] == 0 and summary['expiring_soon'] == 0:
            print("  • All running workspaces are within TTL compliance")
        if summary['stopped'] > 0:
            print(f"  • {summary['stopped']} workspace(s) are already stopped")
        
        print("=" * 80)
    
    def get_workspaces_exceeding_ttl(self, threshold_hours: float = None) -> List[Dict]:
        """
        Get workspaces that are exceeding their TTL
        
        Args:
            threshold_hours: Custom threshold in hours (defaults to config)
            
        Returns:
            List of workspace analyses for workspaces exceeding TTL
        """
        if threshold_hours is None:
            threshold_hours = self.config["ttl_monitor"]["warning_threshold_hours"]
        
        report = self.get_ttl_compliance_report()
        
        # Return expired workspaces and those expiring within threshold
        exceeding = report['workspaces']['expired'].copy()
        
        threshold_seconds = threshold_hours * 3600
        for ws in report['workspaces']['expiring_soon']:
            if ws['seconds_remaining'] <= threshold_seconds:
                exceeding.append(ws)
        
        return exceeding
    
    def monitor_continuous(self, interval_minutes: int = None):
        """
        Run continuous monitoring (for daemon mode)
        
        Args:
            interval_minutes: Check interval in minutes
        """
        import time
        
        if interval_minutes is None:
            interval_minutes = self.config["ttl_monitor"]["check_interval_minutes"]
        
        print(f"Starting TTL monitoring (checking every {interval_minutes} minutes)")
        print("Press Ctrl+C to stop")
        
        try:
            while True:
                print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Running TTL check...")
                
                exceeding = self.get_workspaces_exceeding_ttl()
                if exceeding:
                    print(f"Found {len(exceeding)} workspaces exceeding TTL:")
                    for ws in exceeding:
                        print(f"  - {ws['owner']}/{ws['name']}: {ws['time_remaining']}")
                else:
                    print("All workspaces within TTL compliance")
                
                time.sleep(interval_minutes * 60)
                
        except KeyboardInterrupt:
            print("\nMonitoring stopped by user")

def main():
    """Main function with command line interface"""
    parser = argparse.ArgumentParser(description="Coder TTL Monitor Agent")
    parser.add_argument("--config", default="agents_config.json",
                       help="Configuration file path")
    parser.add_argument("--user", 
                       help="Filter by specific username")
    parser.add_argument("--report", action="store_true",
                       help="Generate compliance report")
    parser.add_argument("--json", action="store_true",
                       help="Output report in JSON format")
    parser.add_argument("--threshold", type=float,
                       help="Custom threshold in hours for expiring workspaces")
    parser.add_argument("--show-all", action="store_true",
                       help="Show all workspaces, not just problematic ones")
    parser.add_argument("--monitor", action="store_true",
                       help="Run continuous monitoring")
    parser.add_argument("--interval", type=int,
                       help="Monitoring interval in minutes")
    
    args = parser.parse_args()
    
    try:
        # Initialize agent
        agent = TTLMonitorAgent(args.config)
        
        # Validate connection
        if not agent.controller.validate_connection():
            print("Error: Could not connect to Coder API")
            sys.exit(1)
        
        # Execute requested action
        if args.monitor:
            agent.monitor_continuous(args.interval)
        elif args.json:
            report = agent.get_ttl_compliance_report(args.user)
            print(json.dumps(report, indent=2))
        else:
            # Default: print compliance report
            agent.print_compliance_report(args.user, args.show_all)
    
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()