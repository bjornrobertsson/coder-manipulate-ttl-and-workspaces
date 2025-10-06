#!/usr/bin/env python3
"""
Prune Workspaces Agent - Identify and cleanup workspaces within user quiet hours periods
Extends the coder-audit-simple project with user-specific quiet hours pruning
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Optional, Tuple
import pytz
from tabulate import tabulate

# Import the workspace controller
from workspace_controller import WorkspaceController

class PruneWorkspacesAgent:
    """Agent for pruning workspaces based on user-specific quiet hours"""
    
    def __init__(self, config_file: str = "agents_config.json"):
        """
        Initialize prune workspaces agent
        
        Args:
            config_file: Path to configuration file
        """
        self.config = self._load_config(config_file)
        self.controller = WorkspaceController()
        self.dry_run = False
        
    def _load_config(self, config_file: str) -> Dict:
        """Load configuration from file or use defaults"""
        default_config = {
            "prune_workspaces": {
                "enabled": True,
                "default_quiet_hours_duration": 8,  # hours
                "timezone": "UTC",
                "include_organizations": [],  # Empty = all orgs
                "exclude_organizations": [],
                "include_groups": [],  # Empty = all groups
                "exclude_groups": [],
                "include_users": [],  # Empty = all users
                "exclude_users": ["admin"],
                "include_templates": [],  # Empty = all templates
                "exclude_templates": []
            },
            "dry_run": False
        }
        
        if os.path.exists(config_file):
            try:
                with open(config_file, 'r') as f:
                    file_config = json.load(f)
                    default_config.update(file_config)
            except Exception as e:
                print(f"Warning: Could not load config file {config_file}: {e}")
        
        return default_config
    
    def _parse_cron_schedule(self, cron_schedule: str) -> Optional[Tuple[str, str, str]]:
        """
        Parse cron schedule to extract time and timezone
        
        Args:
            cron_schedule: Cron schedule string like "CRON_TZ=Europe/London 32 13 * * *"
            
        Returns:
            Tuple of (time_str, timezone_str, raw_schedule) or None if invalid
        """
        try:
            if not cron_schedule or not cron_schedule.startswith("CRON_TZ="):
                return None
            
            # Split "CRON_TZ=Europe/London 32 13 * * *"
            parts = cron_schedule.split(" ")
            if len(parts) < 6:
                return None
            
            # Extract timezone
            timezone_part = parts[0]  # "CRON_TZ=Europe/London"
            timezone_str = timezone_part.split("=")[1]
            
            # Extract time
            minute = parts[1]  # "32"
            hour = parts[2]    # "13"
            time_str = f"{hour}:{minute}"
            
            return time_str, timezone_str, cron_schedule
            
        except Exception as e:
            print(f"Error parsing cron schedule '{cron_schedule}': {e}")
            return None
    
    def get_user_quiet_hours_info(self, username: str = None) -> Optional[Dict]:
        """
        Get user's quiet hours information from enterprise API
        
        Args:
            username: Username to check (defaults to current user)
            
        Returns:
            Dictionary with quiet hours info or None if not available
        """
        try:
            user_schedule = self.controller.get_user_quiet_hours_schedule(username)
            if not user_schedule:
                return None
            
            raw_schedule = user_schedule.get('raw_schedule', '')
            parsed = self._parse_cron_schedule(raw_schedule)
            
            if not parsed:
                return None
            
            time_str, timezone_str, _ = parsed
            
            return {
                'username': username or 'current_user',
                'start_time': time_str,
                'timezone': timezone_str,
                'user_set': user_schedule.get('user_set', False),
                'user_can_set': user_schedule.get('user_can_set', False),
                'next_activation': user_schedule.get('next', None),
                'raw_schedule': raw_schedule
            }
            
        except Exception as e:
            print(f"Error getting quiet hours for user {username}: {e}")
            return None
    
    def is_user_in_quiet_hours(self, user_quiet_hours: Dict, 
                              quiet_hours_duration: int = None) -> Tuple[bool, Optional[datetime], Optional[datetime]]:
        """
        Check if current time is within user's quiet hours period
        
        Args:
            user_quiet_hours: User quiet hours information
            quiet_hours_duration: Duration of quiet hours in hours (defaults to config)
            
        Returns:
            Tuple of (is_in_quiet_hours, quiet_start_time, quiet_end_time)
        """
        try:
            if quiet_hours_duration is None:
                quiet_hours_duration = self.config["prune_workspaces"]["default_quiet_hours_duration"]
            
            # Parse user's timezone and start time
            timezone_str = user_quiet_hours['timezone']
            start_time_str = user_quiet_hours['start_time']  # e.g., "13:32"
            
            # Get current time in user's timezone
            user_tz = pytz.timezone(timezone_str)
            current_time = datetime.now(user_tz)
            
            # Parse start time
            start_hour, start_minute = map(int, start_time_str.split(':'))
            
            # Calculate today's quiet hours start
            quiet_start = current_time.replace(
                hour=start_hour,
                minute=start_minute,
                second=0,
                microsecond=0
            )
            
            # If the start time hasn't occurred today yet, use yesterday's start
            if current_time < quiet_start:
                quiet_start -= timedelta(days=1)
            
            # Calculate quiet hours end (start + duration)
            quiet_end = quiet_start + timedelta(hours=quiet_hours_duration)
            
            # Check if current time is within quiet hours
            is_in_quiet_hours = quiet_start <= current_time <= quiet_end
            
            return is_in_quiet_hours, quiet_start, quiet_end
            
        except Exception as e:
            print(f"Error checking quiet hours for user: {e}")
            return False, None, None
    
    def apply_filters(self, workspaces: List[Dict], filters: Dict) -> List[Dict]:
        """
        Apply comprehensive filtering to workspaces based on organizations, groups, users, and templates
        
        Args:
            workspaces: List of workspaces to filter
            filters: Dictionary containing filter criteria
            
        Returns:
            Filtered list of workspaces
        """
        filtered_workspaces = []
        
        # Cache for user/org/group lookups to avoid repeated API calls
        user_cache = {}
        org_cache = {}
        group_cache = {}
        
        for workspace in workspaces:
            owner_name = workspace.get('owner_name')
            template_id = workspace.get('template_id')
            
            if not owner_name:
                continue
            
            # Get user info (with caching)
            if owner_name not in user_cache:
                users = self.controller.get_users()
                user_info = next((u for u in users if u.get('username') == owner_name), None)
                user_cache[owner_name] = user_info
            
            user_info = user_cache[owner_name]
            if not user_info:
                continue  # Skip if user not found
            
            user_id = user_info.get('id')
            
            # Apply user filters
            if filters.get('include_users'):
                if owner_name not in filters['include_users']:
                    continue
            
            if filters.get('exclude_users'):
                if owner_name in filters['exclude_users']:
                    continue
            
            # Apply template filters
            if filters.get('include_templates'):
                if template_id not in filters['include_templates']:
                    continue
            
            if filters.get('exclude_templates'):
                if template_id in filters['exclude_templates']:
                    continue
            
            # Apply organization filters
            if filters.get('include_organizations') or filters.get('exclude_organizations'):
                if user_id not in org_cache:
                    user_orgs = self.controller.get_user_organizations(user_id)
                    org_cache[user_id] = [org.get('name', '') for org in user_orgs]
                
                user_org_names = org_cache[user_id]
                
                if filters.get('include_organizations'):
                    if not any(org in filters['include_organizations'] for org in user_org_names):
                        continue
                
                if filters.get('exclude_organizations'):
                    if any(org in filters['exclude_organizations'] for org in user_org_names):
                        continue
            
            # Apply group filters
            if filters.get('include_groups') or filters.get('exclude_groups'):
                if user_id not in group_cache:
                    user_groups = self.controller.get_user_groups(user_id)
                    group_cache[user_id] = [group.get('name', '') for group in user_groups]
                
                user_group_names = group_cache[user_id]
                
                if filters.get('include_groups'):
                    if not any(group in filters['include_groups'] for group in user_group_names):
                        continue
                
                if filters.get('exclude_groups'):
                    if any(group in filters['exclude_groups'] for group in user_group_names):
                        continue
            
            # If we get here, the workspace passed all filters
            filtered_workspaces.append(workspace)
        
        return filtered_workspaces
    
    def get_workspaces_in_quiet_hours(self, target_user: str = None, 
                                    quiet_hours_duration: int = None,
                                    include_all_users: bool = False,
                                    custom_filters: Dict = None) -> List[Dict]:
        """
        Get workspaces that are within their owner's quiet hours period
        
        Args:
            target_user: Specific user to check (defaults to current user)
            quiet_hours_duration: Duration of quiet hours in hours
            include_all_users: Whether to check all users or just target user
            
        Returns:
            List of workspaces with quiet hours information
        """
        workspaces_in_quiet_hours = []
        
        # Get all workspaces
        all_workspaces = self.controller.get_workspaces()
        
        # Get users to check
        if include_all_users:
            # For now, we'll check workspaces and try to get quiet hours for each unique owner
            unique_owners = set(ws.get('owner_name') for ws in all_workspaces if ws.get('owner_name'))
            users_to_check = list(unique_owners)
        elif target_user:
            users_to_check = [target_user]
        else:
            # Default to current user
            current_user = self.controller.get_current_user()
            if current_user:
                users_to_check = [current_user.get('username')]
            else:
                users_to_check = []
        
        # Apply comprehensive filters
        filter_config = self.config["prune_workspaces"]
        
        # Merge custom filters with config
        filters = {
            'include_organizations': custom_filters.get('include_organizations', []) if custom_filters else filter_config.get('include_organizations', []),
            'exclude_organizations': custom_filters.get('exclude_organizations', []) if custom_filters else filter_config.get('exclude_organizations', []),
            'include_groups': custom_filters.get('include_groups', []) if custom_filters else filter_config.get('include_groups', []),
            'exclude_groups': custom_filters.get('exclude_groups', []) if custom_filters else filter_config.get('exclude_groups', []),
            'include_users': custom_filters.get('include_users', []) if custom_filters else filter_config.get('include_users', []),
            'exclude_users': custom_filters.get('exclude_users', []) if custom_filters else filter_config.get('exclude_users', []),
            'include_templates': custom_filters.get('include_templates', []) if custom_filters else filter_config.get('include_templates', []),
            'exclude_templates': custom_filters.get('exclude_templates', []) if custom_filters else filter_config.get('exclude_templates', [])
        }
        
        # Apply filters to all workspaces first
        filtered_workspaces = self.apply_filters(all_workspaces, filters)
        
        # Then filter by users to check
        if not include_all_users:
            filtered_workspaces = [ws for ws in filtered_workspaces if ws.get('owner_name') in users_to_check]
        
        # Check each user's quiet hours
        user_quiet_hours_cache = {}
        
        for workspace in filtered_workspaces:
            owner = workspace.get('owner_name')
            if not owner:
                continue
            
            # Get user's quiet hours info (use cache to avoid repeated API calls)
            if owner not in user_quiet_hours_cache:
                user_quiet_hours_cache[owner] = self.get_user_quiet_hours_info(owner)
            
            user_quiet_hours = user_quiet_hours_cache[owner]
            if not user_quiet_hours:
                continue  # User doesn't have quiet hours configured
            
            # Check if user is currently in quiet hours
            is_in_quiet, quiet_start, quiet_end = self.is_user_in_quiet_hours(
                user_quiet_hours, quiet_hours_duration
            )
            
            if is_in_quiet:
                # Add quiet hours information to workspace
                workspace_info = workspace.copy()
                workspace_info['quiet_hours_info'] = {
                    'user_quiet_hours': user_quiet_hours,
                    'quiet_start': quiet_start.isoformat() if quiet_start else None,
                    'quiet_end': quiet_end.isoformat() if quiet_end else None,
                    'is_in_quiet_hours': True
                }
                workspaces_in_quiet_hours.append(workspace_info)
        
        return workspaces_in_quiet_hours
    
    def print_workspaces_in_quiet_hours(self, workspaces: List[Dict]):
        """
        Print formatted list of workspaces in quiet hours
        
        Args:
            workspaces: List of workspaces with quiet hours info
        """
        if not workspaces:
            print("\n✅ No workspaces found within quiet hours periods")
            return
        
        print(f"\n🌙 WORKSPACES WITHIN QUIET HOURS PERIODS ({len(workspaces)})")
        print("=" * 80)
        
        # Group by user for better organization
        workspaces_by_user = {}
        for ws in workspaces:
            owner = ws.get('owner_name', 'Unknown')
            if owner not in workspaces_by_user:
                workspaces_by_user[owner] = []
            workspaces_by_user[owner].append(ws)
        
        for owner, user_workspaces in workspaces_by_user.items():
            # Get quiet hours info from first workspace
            quiet_info = user_workspaces[0].get('quiet_hours_info', {})
            user_qh = quiet_info.get('user_quiet_hours', {})
            
            print(f"\n👤 {owner}")
            print(f"   Quiet Hours: {user_qh.get('start_time', 'N/A')} ({user_qh.get('timezone', 'N/A')})")
            if quiet_info.get('quiet_start') and quiet_info.get('quiet_end'):
                start_time = datetime.fromisoformat(quiet_info['quiet_start'])
                end_time = datetime.fromisoformat(quiet_info['quiet_end'])
                print(f"   Current Period: {start_time.strftime('%H:%M')} - {end_time.strftime('%H:%M')}")
            print("-" * 60)
            
            # Create table for user's workspaces
            table_data = []
            for ws in user_workspaces:
                status = ws.get('latest_build', {}).get('status', 'Unknown')
                template_id = ws.get('template_id', 'Unknown')
                
                # Get template name
                template_map = getattr(self.controller, '_template_map', None)
                if not template_map:
                    self.controller._template_map = self.controller.get_template_map()
                    template_map = self.controller._template_map
                
                template_name = template_map.get(template_id, template_id)
                
                table_data.append([
                    ws.get('name', 'Unknown'),
                    template_name,
                    status,
                    ws.get('created_at', 'N/A')[:10] if ws.get('created_at') else 'N/A'  # Just date
                ])
            
            headers = ["Workspace", "Template", "Status", "Created"]
            print(tabulate(table_data, headers=headers, tablefmt="simple"))
            print()
    
    def cleanup_workspaces(self, workspaces: List[Dict], 
                          reason: str = "Pruned during quiet hours") -> Dict[str, bool]:
        """
        Stop/cleanup workspaces that are in quiet hours
        
        Args:
            workspaces: List of workspaces to cleanup
            reason: Reason for stopping
            
        Returns:
            Dictionary mapping workspace_id to success status
        """
        if not workspaces:
            print("\n✅ No workspaces to cleanup")
            return {}
        
        # Filter to only running workspaces
        running_workspaces = [
            ws for ws in workspaces 
            if ws.get('latest_build', {}).get('status') == 'running'
        ]
        
        if not running_workspaces:
            print(f"\n✅ No running workspaces to cleanup (found {len(workspaces)} total, all already stopped)")
            return {}
        
        print(f"\n{'🧪 [DRY RUN] ' if self.dry_run else '🛑 '}Cleaning up {len(running_workspaces)} running workspaces:")
        print("-" * 60)
        
        results = {}
        for ws in running_workspaces:
            workspace_id = ws['id']
            summary = self.controller.workspace_summary(ws)
            owner = ws.get('owner_name', 'Unknown')
            
            if self.dry_run:
                print(f"  🧪 [DRY RUN] Would stop: {summary}")
                print(f"     Owner: {owner}")
                print(f"     Reason: {reason}")
                results[workspace_id] = True
            else:
                print(f"  🛑 Stopping: {summary}")
                print(f"     Owner: {owner}")
                print(f"     Reason: {reason}")
                success = self.controller.stop_workspace(workspace_id, reason)
                results[workspace_id] = success
                print(f"     Result: {'✅ Success' if success else '❌ Failed'}")
        
        return results

def main():
    """Main function with command line interface"""
    parser = argparse.ArgumentParser(description="Coder Prune Workspaces Agent")
    parser.add_argument("--config", default="agents_config.json",
                       help="Configuration file path")
    parser.add_argument("--user", 
                       help="Target specific user (defaults to current user)")
    parser.add_argument("--all", action="store_true",
                       help="Check all users, not just current user")
    parser.add_argument("--duration", type=int, default=8,
                       help="Quiet hours duration in hours (default: 8)")
    parser.add_argument("--cleanup", action="store_true",
                       help="Actually stop workspaces (cleanup mode)")
    parser.add_argument("--dry-run", action="store_true",
                       help="Show what would be done without executing")
    parser.add_argument("--json", action="store_true",
                       help="Output results in JSON format")
    
    # Organization filters
    parser.add_argument("--include-org", action="append", dest="include_organizations",
                       help="Include specific organizations (can be used multiple times)")
    parser.add_argument("--exclude-org", action="append", dest="exclude_organizations",
                       help="Exclude specific organizations (can be used multiple times)")
    
    # Group filters
    parser.add_argument("--include-group", action="append", dest="include_groups",
                       help="Include specific groups (can be used multiple times)")
    parser.add_argument("--exclude-group", action="append", dest="exclude_groups",
                       help="Exclude specific groups (can be used multiple times)")
    
    # User filters
    parser.add_argument("--include-user", action="append", dest="include_users",
                       help="Include specific users (can be used multiple times)")
    parser.add_argument("--exclude-user", action="append", dest="exclude_users",
                       help="Exclude specific users (can be used multiple times)")
    
    # Template filters
    parser.add_argument("--include-template", action="append", dest="include_templates",
                       help="Include specific templates (can be used multiple times)")
    parser.add_argument("--exclude-template", action="append", dest="exclude_templates",
                       help="Exclude specific templates (can be used multiple times)")
    
    args = parser.parse_args()
    
    try:
        # Initialize agent
        agent = PruneWorkspacesAgent(args.config)
        
        # Set dry run mode
        if args.dry_run:
            agent.dry_run = True
        
        # Validate connection
        if not agent.controller.validate_connection():
            print("Error: Could not connect to Coder API")
            sys.exit(1)
        
        # Build custom filters from command line arguments
        custom_filters = {}
        if args.include_organizations:
            custom_filters['include_organizations'] = args.include_organizations
        if args.exclude_organizations:
            custom_filters['exclude_organizations'] = args.exclude_organizations
        if args.include_groups:
            custom_filters['include_groups'] = args.include_groups
        if args.exclude_groups:
            custom_filters['exclude_groups'] = args.exclude_groups
        if args.include_users:
            custom_filters['include_users'] = args.include_users
        if args.exclude_users:
            custom_filters['exclude_users'] = args.exclude_users
        if args.include_templates:
            custom_filters['include_templates'] = args.include_templates
        if args.exclude_templates:
            custom_filters['exclude_templates'] = args.exclude_templates
        
        # Get workspaces in quiet hours
        workspaces = agent.get_workspaces_in_quiet_hours(
            target_user=args.user,
            quiet_hours_duration=args.duration,
            include_all_users=args.all,
            custom_filters=custom_filters if custom_filters else None
        )
        
        if args.json:
            # Output in JSON format
            output = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "target_user": args.user,
                "include_all_users": args.all,
                "quiet_hours_duration": args.duration,
                "total_workspaces": len(workspaces),
                "workspaces": workspaces
            }
            print(json.dumps(output, indent=2, default=str))
        else:
            # Human-readable output
            agent.print_workspaces_in_quiet_hours(workspaces)
        
        # Cleanup if requested
        if args.cleanup:
            if args.json:
                print("\n" + "="*50 + " CLEANUP RESULTS " + "="*50, file=sys.stderr)
            
            results = agent.cleanup_workspaces(workspaces)
            
            success_count = sum(1 for success in results.values() if success)
            total_count = len(results)
            
            if not args.json:
                print(f"\n📊 Cleanup completed: {success_count}/{total_count} workspaces processed successfully")
                
                if success_count < total_count:
                    print("⚠️  Some operations failed. Check logs for details.")
                    sys.exit(1)
            else:
                cleanup_summary = {
                    "cleanup_executed": True,
                    "total_processed": total_count,
                    "successful": success_count,
                    "failed": total_count - success_count,
                    "results": results
                }
                print(json.dumps(cleanup_summary, indent=2), file=sys.stderr)
    
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()