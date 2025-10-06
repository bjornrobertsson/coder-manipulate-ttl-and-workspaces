#!/usr/bin/env python3
"""
Quiet Hours Agent - Detect quiet hours and stop workspaces after grace period
Extends the coder-audit-simple project with intelligent workspace stopping
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Optional
import pytz

# Import the workspace controller
from workspace_controller import WorkspaceController

class QuietHoursAgent:
    """Agent for managing workspaces during quiet hours"""
    
    def __init__(self, config_file: str = "agents_config.json"):
        """
        Initialize quiet hours agent
        
        Args:
            config_file: Path to configuration file
        """
        self.config = self._load_config(config_file)
        self.controller = WorkspaceController()
        self.dry_run = self.config.get('dry_run', False)
        
        # Validate configuration
        self._validate_config()
    
    def _load_config(self, config_file: str) -> Dict:
        """Load configuration from file or use defaults"""
        default_config = {
            "quiet_hours": {
                "enabled": True,
                "start_time": "18:00",
                "end_time": "08:00",
                "timezone": "UTC",
                "grace_period_hours": 1,
                "excluded_users": [],
                "excluded_templates": []
            },
            "dry_run": False,
            "logging": {
                "level": "INFO",
                "file": "quiet_hours.log"
            }
        }
        
        if os.path.exists(config_file):
            try:
                with open(config_file, 'r') as f:
                    file_config = json.load(f)
                    # Merge with defaults
                    default_config.update(file_config)
            except Exception as e:
                print(f"Warning: Could not load config file {config_file}: {e}")
                print("Using default configuration")
        
        # Override with environment variables if present
        env_overrides = {
            "start_time": os.environ.get("QUIET_HOURS_START"),
            "end_time": os.environ.get("QUIET_HOURS_END"),
            "timezone": os.environ.get("QUIET_HOURS_TIMEZONE"),
            "grace_period_hours": os.environ.get("GRACE_PERIOD_HOURS"),
            "dry_run": os.environ.get("DRY_RUN", "").lower() == "true"
        }
        
        for key, value in env_overrides.items():
            if value is not None:
                if key == "grace_period_hours":
                    default_config["quiet_hours"][key] = int(value)
                elif key == "dry_run":
                    default_config[key] = value
                else:
                    default_config["quiet_hours"][key] = value
        
        return default_config
    
    def _validate_config(self):
        """Validate configuration parameters"""
        qh_config = self.config["quiet_hours"]
        
        # Validate time format
        try:
            datetime.strptime(qh_config["start_time"], "%H:%M")
            datetime.strptime(qh_config["end_time"], "%H:%M")
        except ValueError as e:
            raise ValueError(f"Invalid time format in configuration: {e}")
        
        # Validate timezone
        try:
            pytz.timezone(qh_config["timezone"])
        except pytz.exceptions.UnknownTimeZoneError as e:
            raise ValueError(f"Invalid timezone in configuration: {e}")
        
        # Validate grace period
        if qh_config["grace_period_hours"] < 0:
            raise ValueError("Grace period cannot be negative")
    
    def _get_current_time(self) -> datetime:
        """Get current time in configured timezone"""
        tz = pytz.timezone(self.config["quiet_hours"]["timezone"])
        return datetime.now(tz)
    
    def _parse_time(self, time_str: str) -> datetime.time:
        """Parse time string to time object"""
        return datetime.strptime(time_str, "%H:%M").time()
    
    def is_quiet_hours(self, check_time: datetime = None) -> bool:
        """
        Check if current time is within quiet hours
        
        Args:
            check_time: Time to check (defaults to current time)
            
        Returns:
            True if within quiet hours, False otherwise
        """
        if not self.config["quiet_hours"]["enabled"]:
            return False
        
        if check_time is None:
            check_time = self._get_current_time()
        
        qh_config = self.config["quiet_hours"]
        start_time = self._parse_time(qh_config["start_time"])
        end_time = self._parse_time(qh_config["end_time"])
        current_time = check_time.time()
        
        # Handle overnight quiet hours (e.g., 18:00 to 08:00)
        if start_time > end_time:
            return current_time >= start_time or current_time <= end_time
        else:
            return start_time <= current_time <= end_time
    
    def get_quiet_hours_start_today(self) -> datetime:
        """Get the quiet hours start time for today"""
        current = self._get_current_time()
        qh_config = self.config["quiet_hours"]
        start_time = self._parse_time(qh_config["start_time"])
        
        # Create datetime for today's quiet hours start
        start_datetime = current.replace(
            hour=start_time.hour,
            minute=start_time.minute,
            second=0,
            microsecond=0
        )
        
        # If quiet hours start time has passed today, it refers to yesterday's start
        if current.time() < start_time:
            start_datetime -= timedelta(days=1)
        
        return start_datetime
    
    def is_grace_period_over(self) -> bool:
        """
        Check if grace period after quiet hours start has ended
        
        Returns:
            True if grace period is over and workspaces should be stopped
        """
        if not self.is_quiet_hours():
            return False
        
        quiet_start = self.get_quiet_hours_start_today()
        grace_period = timedelta(hours=self.config["quiet_hours"]["grace_period_hours"])
        grace_end = quiet_start + grace_period
        
        current = self._get_current_time()
        return current >= grace_end
    
    def _format_time_remaining(self, deadline_str: str) -> tuple:
        """
        Format time remaining until deadline
        
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
    
    def is_past_quiet_hours_end(self) -> bool:
        """
        Check if current time is past the quiet hours end time
        
        Returns:
            True if past quiet hours end time
        """
        current = self._get_current_time()
        qh_config = self.config["quiet_hours"]
        end_time = self._parse_time(qh_config["end_time"])
        
        # Create datetime for today's quiet hours end
        end_datetime = current.replace(
            hour=end_time.hour,
            minute=end_time.minute,
            second=0,
            microsecond=0
        )
        
        # Handle overnight quiet hours
        start_time = self._parse_time(qh_config["start_time"])
        if start_time > end_time:
            # Overnight quiet hours - end time is next day
            if current.time() >= start_time:
                # We're after start time, so end time is tomorrow
                end_datetime += timedelta(days=1)
        
        return current > end_datetime
    
    def categorize_workspaces(self) -> Dict[str, List[Dict]]:
        """
        Categorize all running workspaces based on quiet hours and TTL status
        
        Returns:
            Dictionary with categorized workspace lists
        """
        qh_config = self.config["quiet_hours"]
        
        # Get all running workspaces
        all_running = self.controller.get_running_workspaces()
        
        # Filter out excluded users and templates for quiet hours analysis
        quiet_hours_eligible = []
        excluded_workspaces = []
        
        for ws in all_running:
            if (ws.get('owner_name') in qh_config["excluded_users"] or 
                ws.get('template_id') in qh_config["excluded_templates"]):
                excluded_workspaces.append(ws)
            else:
                quiet_hours_eligible.append(ws)
        
        # Categorize workspaces
        categories = {
            "quiet_hours_stopping": [],      # In quiet hours, grace period over
            "quiet_hours_grace": [],         # In quiet hours, grace period active
            "past_quiet_hours_end": [],      # Running past quiet hours end time
            "ttl_expired": [],               # TTL expired (should have stopped)
            "normal_running": [],            # Running normally
            "excluded": excluded_workspaces  # Excluded from quiet hours
        }
        
        is_quiet = self.is_quiet_hours()
        grace_over = self.is_grace_period_over()
        past_end = self.is_past_quiet_hours_end()
        
        for ws in quiet_hours_eligible:
            # Check TTL status
            deadline = ws.get('latest_build', {}).get('deadline')
            time_remaining, seconds_remaining, is_expired = self._format_time_remaining(deadline)
            
            # Add TTL info to workspace
            ws['ttl_info'] = {
                'deadline': deadline,
                'time_remaining': time_remaining,
                'seconds_remaining': seconds_remaining,
                'is_expired': is_expired
            }
            
            # Categorize based on status
            if is_expired:
                categories["ttl_expired"].append(ws)
            elif is_quiet and grace_over:
                categories["quiet_hours_stopping"].append(ws)
            elif is_quiet and not grace_over:
                categories["quiet_hours_grace"].append(ws)
            elif past_end and not is_quiet:
                categories["past_quiet_hours_end"].append(ws)
            else:
                categories["normal_running"].append(ws)
        
        return categories
    
    def get_workspaces_to_stop(self) -> List[Dict]:
        """
        Get list of workspaces that should be stopped during quiet hours
        
        Returns:
            List of workspace dictionaries that should be stopped
        """
        categories = self.categorize_workspaces()
        return categories["quiet_hours_stopping"]
    
    def get_ttl_expired_workspaces(self) -> List[Dict]:
        """
        Get list of workspaces that have exceeded their TTL
        
        Returns:
            List of workspace dictionaries with expired TTL
        """
        categories = self.categorize_workspaces()
        return categories["ttl_expired"]
    
    def print_workspace_categories(self):
        """
        Print detailed categorization of all workspaces
        """
        categories = self.categorize_workspaces()
        
        print("\n" + "=" * 80)
        print("WORKSPACE CATEGORIZATION")
        print("=" * 80)
        
        # Quiet hours stopping
        if categories["quiet_hours_stopping"]:
            print(f"\n🛑 QUIET HOURS - STOPPING NOW ({len(categories['quiet_hours_stopping'])})")
            print("-" * 60)
            for ws in categories["quiet_hours_stopping"]:
                ttl_info = ws.get('ttl_info', {})
                print(f"  • {self.controller.workspace_summary(ws)}")
                print(f"    TTL: {ttl_info.get('time_remaining', 'N/A')}")
        
        # Quiet hours grace period
        if categories["quiet_hours_grace"]:
            print(f"\n⏰ QUIET HOURS - GRACE PERIOD ({len(categories['quiet_hours_grace'])})")
            print("-" * 60)
            for ws in categories["quiet_hours_grace"]:
                ttl_info = ws.get('ttl_info', {})
                print(f"  • {self.controller.workspace_summary(ws)}")
                print(f"    TTL: {ttl_info.get('time_remaining', 'N/A')}")
        
        # Past quiet hours end
        if categories["past_quiet_hours_end"]:
            print(f"\n🌅 RUNNING PAST QUIET HOURS END ({len(categories['past_quiet_hours_end'])})")
            print("-" * 60)
            for ws in categories["past_quiet_hours_end"]:
                ttl_info = ws.get('ttl_info', {})
                print(f"  • {self.controller.workspace_summary(ws)}")
                print(f"    TTL: {ttl_info.get('time_remaining', 'N/A')}")
        
        # TTL expired
        if categories["ttl_expired"]:
            print(f"\n💀 TTL EXPIRED - SHOULD HAVE STOPPED ({len(categories['ttl_expired'])})")
            print("-" * 60)
            for ws in categories["ttl_expired"]:
                ttl_info = ws.get('ttl_info', {})
                print(f"  • {self.controller.workspace_summary(ws)}")
                print(f"    TTL: {ttl_info.get('time_remaining', 'N/A')}")
        
        # Normal running
        if categories["normal_running"]:
            print(f"\n✅ RUNNING NORMALLY ({len(categories['normal_running'])})")
            print("-" * 60)
            for ws in categories["normal_running"]:
                ttl_info = ws.get('ttl_info', {})
                print(f"  • {self.controller.workspace_summary(ws)}")
                print(f"    TTL: {ttl_info.get('time_remaining', 'N/A')}")
        
        # Excluded
        if categories["excluded"]:
            print(f"\n🚫 EXCLUDED FROM QUIET HOURS ({len(categories['excluded'])})")
            print("-" * 60)
            for ws in categories["excluded"]:
                print(f"  • {self.controller.workspace_summary(ws)}")
                reason = "User excluded" if ws.get('owner_name') in self.config["quiet_hours"]["excluded_users"] else "Template excluded"
                print(f"    Reason: {reason}")
        
        print("\n" + "=" * 80)
    
    def stop_workspaces_for_quiet_hours(self, force_ttl: bool = False) -> Dict[str, bool]:
        """
        Stop workspaces for quiet hours and optionally force stop TTL-expired workspaces
        
        Args:
            force_ttl: If True, also stop workspaces that have exceeded their TTL
            
        Returns:
            Dictionary mapping workspace_id to success status
        """
        results = {}
        
        # Get workspace categories
        categories = self.categorize_workspaces()
        
        # Print categorization
        self.print_workspace_categories()
        
        # Determine which workspaces to stop
        workspaces_to_stop = []
        stop_reasons = {}
        
        # Add quiet hours workspaces if grace period is over
        if self.is_grace_period_over():
            for ws in categories["quiet_hours_stopping"]:
                workspaces_to_stop.append(ws)
                stop_reasons[ws['id']] = "Quiet hours policy"
        
        # Add TTL expired workspaces if force flag is set
        if force_ttl:
            for ws in categories["ttl_expired"]:
                if ws not in workspaces_to_stop:  # Avoid duplicates
                    workspaces_to_stop.append(ws)
                    stop_reasons[ws['id']] = "TTL expired"
        
        if not workspaces_to_stop:
            if not self.is_grace_period_over() and not force_ttl:
                print("\n⏰ Grace period not over yet, no workspaces will be stopped")
                print("💡 Use --force to stop TTL-expired workspaces regardless of quiet hours")
            elif not self.is_grace_period_over() and force_ttl and not categories["ttl_expired"]:
                print("\n✅ No TTL-expired workspaces found to force stop")
            else:
                print("\n✅ No workspaces to stop")
            return {}
        
        print(f"\n{'🧪 [DRY RUN] ' if self.dry_run else '🛑 '}Stopping {len(workspaces_to_stop)} workspaces:")
        print("-" * 60)
        
        for ws in workspaces_to_stop:
            workspace_id = ws['id']
            summary = self.controller.workspace_summary(ws)
            reason = stop_reasons[workspace_id]
            ttl_info = ws.get('ttl_info', {})
            
            if self.dry_run:
                print(f"  🧪 [DRY RUN] Would stop: {summary}")
                print(f"     Reason: {reason}")
                print(f"     TTL: {ttl_info.get('time_remaining', 'N/A')}")
                results[workspace_id] = True
            else:
                print(f"  🛑 Stopping: {summary}")
                print(f"     Reason: {reason}")
                print(f"     TTL: {ttl_info.get('time_remaining', 'N/A')}")
                success = self.controller.stop_workspace(
                    workspace_id, 
                    f"Automated stop - {reason.lower()}"
                )
                results[workspace_id] = success
                print(f"     Result: {'✅ Success' if success else '❌ Failed'}")
        
        return results
    
    def generate_report(self) -> Dict:
        """
        Generate a comprehensive quiet hours report
        
        Returns:
            Report dictionary with current status and recommendations
        """
        current_time = self._get_current_time()
        is_quiet = self.is_quiet_hours()
        grace_over = self.is_grace_period_over()
        workspaces_to_stop = self.get_workspaces_to_stop()
        
        report = {
            "timestamp": current_time.isoformat(),
            "timezone": self.config["quiet_hours"]["timezone"],
            "quiet_hours_active": is_quiet,
            "grace_period_over": grace_over,
            "workspaces_running": len(self.controller.get_running_workspaces()),
            "workspaces_to_stop": len(workspaces_to_stop),
            "excluded_users": self.config["quiet_hours"]["excluded_users"],
            "excluded_templates": self.config["quiet_hours"]["excluded_templates"],
            "workspaces": []
        }
        
        # Add workspace details
        for ws in workspaces_to_stop:
            report["workspaces"].append({
                "id": ws['id'],
                "owner": ws.get('owner_name'),
                "name": ws.get('name'),
                "template_id": ws.get('template_id'),
                "status": ws.get('latest_build', {}).get('status'),
                "summary": self.controller.workspace_summary(ws)
            })
        
        if is_quiet:
            quiet_start = self.get_quiet_hours_start_today()
            grace_end = quiet_start + timedelta(hours=self.config["quiet_hours"]["grace_period_hours"])
            
            report["quiet_hours_started"] = quiet_start.isoformat()
            report["grace_period_ends"] = grace_end.isoformat()
            
            if grace_over:
                report["action_required"] = "Stop workspaces now"
            else:
                time_until_stop = grace_end - current_time
                report["action_required"] = f"Stop workspaces in {time_until_stop}"
        else:
            report["action_required"] = "No action required - outside quiet hours"
        
        return report
    
    def print_status(self):
        """Print current quiet hours status"""
        report = self.generate_report()
        
        print("=" * 60)
        print("QUIET HOURS AGENT STATUS")
        print("=" * 60)
        print(f"Current Time: {report['timestamp']}")
        print(f"Timezone: {report['timezone']}")
        print(f"Quiet Hours Active: {'Yes' if report['quiet_hours_active'] else 'No'}")
        print(f"Grace Period Over: {'Yes' if report['grace_period_over'] else 'No'}")
        print(f"Running Workspaces: {report['workspaces_running']}")
        print(f"Workspaces to Stop: {report['workspaces_to_stop']}")
        print(f"Action Required: {report['action_required']}")
        
        if report['excluded_users']:
            print(f"Excluded Users: {', '.join(report['excluded_users'])}")
        
        if report['excluded_templates']:
            print(f"Excluded Templates: {', '.join(report['excluded_templates'])}")
        
        if report['workspaces']:
            print("\nWorkspaces that would be stopped:")
            for ws in report['workspaces']:
                print(f"  - {ws['summary']}")
        
        print("=" * 60)
        
        # Include enterprise quiet hours information
        print("\n")
        self.controller.print_enterprise_quiet_hours()

def main():
    """Main function with command line interface"""
    parser = argparse.ArgumentParser(description="Coder Quiet Hours Agent")
    parser.add_argument("--config", default="agents_config.json", 
                       help="Configuration file path")
    parser.add_argument("--dry-run", action="store_true", 
                       help="Show what would be done without executing")
    parser.add_argument("--execute", action="store_true", 
                       help="Execute quiet hours stopping")
    parser.add_argument("--status", action="store_true", 
                       help="Show current status")
    parser.add_argument("--report", action="store_true", 
                       help="Generate JSON report")
    parser.add_argument("--timezone", 
                       help="Override timezone for this run")
    parser.add_argument("--enterprise", action="store_true",
                       help="Show enterprise quiet hours configuration only")
    parser.add_argument("--force", action="store_true",
                       help="Force stop workspaces that have exceeded their TTL")
    parser.add_argument("--categorize", action="store_true",
                       help="Show detailed workspace categorization")
    
    args = parser.parse_args()
    
    try:
        # Initialize agent
        agent = QuietHoursAgent(args.config)
        
        # Override dry run if specified
        if args.dry_run:
            agent.dry_run = True
        
        # Override timezone if specified
        if args.timezone:
            agent.config["quiet_hours"]["timezone"] = args.timezone
            agent._validate_config()
        
        # Validate connection
        if not agent.controller.validate_connection():
            print("Error: Could not connect to Coder API")
            sys.exit(1)
        
        # Execute requested action
        if args.enterprise:
            agent.controller.print_enterprise_quiet_hours()
        elif args.status:
            agent.print_status()
        elif args.report:
            report = agent.generate_report()
            print(json.dumps(report, indent=2))
        elif args.categorize:
            agent.print_workspace_categories()
        elif args.execute:
            results = agent.stop_workspaces_for_quiet_hours(force_ttl=args.force)
            
            success_count = sum(1 for success in results.values() if success)
            total_count = len(results)
            
            print(f"\n📊 Operation completed: {success_count}/{total_count} workspaces stopped successfully")
            
            if success_count < total_count:
                print("⚠️  Some operations failed. Check logs for details.")
                sys.exit(1)
        else:
            # Default: show status
            agent.print_status()
    
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()