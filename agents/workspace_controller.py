#!/usr/bin/env python3
"""
Workspace Controller - Core API wrapper for workspace control operations
Extends the coder-audit-simple project with workspace stopping capabilities
"""

import requests
import json
import os
import sys
import time
from datetime import datetime, timezone
from typing import List, Dict, Optional, Any

class WorkspaceController:
    """Core controller for Coder workspace operations"""
    
    def __init__(self, coder_url: str = None, token: str = None):
        """
        Initialize workspace controller
        
        Args:
            coder_url: Coder instance URL (defaults to CODER_URL env var)
            token: API token (defaults to CODER_TOKEN env var or audit-token.txt)
        """
        self.coder_url = coder_url or self._get_coder_url()
        self.token = token or self._get_token()
        self.headers = {
            'Accept': 'application/json',
            'Coder-Session-Token': self.token,
            'Content-Type': 'application/json'
        }
    
    def _get_token(self) -> str:
        """Get API token from file or environment variable"""
        if os.path.exists("audit-token.txt"):
            with open("audit-token.txt", "r") as f:
                return f.read().strip()
        
        token = os.environ.get("CODER_TOKEN")
        if token:
            return token
        
        raise ValueError("No API token found. Set CODER_TOKEN env var or create audit-token.txt")
    
    def _get_coder_url(self) -> str:
        """Get Coder URL from environment variable"""
        url = os.environ.get("CODER_URL")
        if not url:
            raise ValueError("CODER_URL environment variable is required")
        
        # Ensure URL has https:// prefix
        if not url.startswith(('http://', 'https://')):
            url = f"https://{url}"
        
        return url.rstrip('/')
    
    def _make_request(self, method: str, endpoint: str, data: Dict = None, retries: int = 3) -> Dict:
        """
        Make API request with error handling and retries
        
        Args:
            method: HTTP method (GET, POST, PUT, DELETE)
            endpoint: API endpoint (without base URL)
            data: Request payload for POST/PUT requests
            retries: Number of retry attempts
            
        Returns:
            Response JSON data
            
        Raises:
            Exception: If request fails after all retries
        """
        url = f"{self.coder_url}{endpoint}"
        
        for attempt in range(retries + 1):
            try:
                if method.upper() == 'GET':
                    response = requests.get(url, headers=self.headers, timeout=30)
                elif method.upper() == 'POST':
                    response = requests.post(url, headers=self.headers, 
                                           data=json.dumps(data) if data else None, timeout=30)
                elif method.upper() == 'PUT':
                    response = requests.put(url, headers=self.headers, 
                                          data=json.dumps(data) if data else None, timeout=30)
                elif method.upper() == 'DELETE':
                    response = requests.delete(url, headers=self.headers, timeout=30)
                else:
                    raise ValueError(f"Unsupported HTTP method: {method}")
                
                if response.status_code in [200, 201, 204]:
                    return response.json() if response.content else {}
                elif response.status_code == 404:
                    raise Exception(f"Resource not found: {endpoint}")
                elif response.status_code == 403:
                    raise Exception(f"Permission denied: {endpoint}")
                else:
                    raise Exception(f"API error {response.status_code}: {response.text}")
                    
            except requests.exceptions.RequestException as e:
                if attempt < retries:
                    wait_time = 2 ** attempt  # Exponential backoff
                    print(f"Request failed (attempt {attempt + 1}/{retries + 1}), retrying in {wait_time}s: {e}")
                    time.sleep(wait_time)
                else:
                    raise Exception(f"Request failed after {retries + 1} attempts: {e}")
    
    def get_workspaces(self, filters: Dict = None) -> List[Dict]:
        """
        Get all workspaces with optional filtering
        
        Args:
            filters: Optional filters (status, owner, template)
            
        Returns:
            List of workspace dictionaries
        """
        try:
            response = self._make_request('GET', '/api/v2/workspaces')
            workspaces = response.get('workspaces', [])
            
            if filters:
                filtered_workspaces = []
                for ws in workspaces:
                    include = True
                    
                    if 'status' in filters:
                        ws_status = ws.get('latest_build', {}).get('status')
                        if ws_status != filters['status']:
                            include = False
                    
                    if 'owner' in filters and include:
                        if ws.get('owner_name') != filters['owner']:
                            include = False
                    
                    if 'template' in filters and include:
                        if ws.get('template_id') != filters['template']:
                            include = False
                    
                    if include:
                        filtered_workspaces.append(ws)
                
                return filtered_workspaces
            
            return workspaces
            
        except Exception as e:
            print(f"Error fetching workspaces: {e}")
            return []
    
    def get_running_workspaces(self, exclude_users: List[str] = None, 
                              exclude_templates: List[str] = None) -> List[Dict]:
        """
        Get all currently running workspaces with exclusions
        
        Args:
            exclude_users: List of usernames to exclude
            exclude_templates: List of template IDs to exclude
            
        Returns:
            List of running workspace dictionaries
        """
        workspaces = self.get_workspaces({'status': 'running'})
        
        if exclude_users or exclude_templates:
            filtered = []
            for ws in workspaces:
                if exclude_users and ws.get('owner_name') in exclude_users:
                    continue
                if exclude_templates and ws.get('template_id') in exclude_templates:
                    continue
                filtered.append(ws)
            return filtered
        
        return workspaces
    
    def stop_workspace(self, workspace_id: str, reason: str = "Automated stop") -> bool:
        """
        Stop a specific workspace
        
        Args:
            workspace_id: Workspace ID to stop
            reason: Reason for stopping (for logging only, not sent to API)
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Create a stop build for the workspace
            # Note: The reason field seems to have validation constraints in the API
            # so we'll try different approaches
            
            # First try with just the transition
            build_data = {
                "transition": "stop"
            }
            
            endpoint = f"/api/v2/workspaces/{workspace_id}/builds"
            
            try:
                response = self._make_request('POST', endpoint, build_data)
                print(f"Successfully initiated stop for workspace {workspace_id}: {reason}")
                return True
            except Exception as api_error:
                # If that fails, try with a standard reason
                if "reason" in str(api_error).lower():
                    # Try with common valid reasons
                    valid_reasons = ["initiator", "autostart", "autostop", "shutdown"]
                    
                    for valid_reason in valid_reasons:
                        try:
                            build_data_with_reason = {
                                "transition": "stop",
                                "reason": valid_reason
                            }
                            response = self._make_request('POST', endpoint, build_data_with_reason)
                            print(f"Successfully initiated stop for workspace {workspace_id}: {reason} (API reason: {valid_reason})")
                            return True
                        except Exception:
                            continue
                
                # If all attempts fail, re-raise the original error
                raise api_error
            
        except Exception as e:
            print(f"Failed to stop workspace {workspace_id}: {e}")
            return False
    
    def bulk_stop_workspaces(self, workspace_ids: List[str], reason: str = "Bulk stop", 
                           max_concurrent: int = 5) -> Dict[str, bool]:
        """
        Stop multiple workspaces with rate limiting
        
        Args:
            workspace_ids: List of workspace IDs to stop
            reason: Reason for stopping
            max_concurrent: Maximum concurrent stop operations
            
        Returns:
            Dictionary mapping workspace_id to success status
        """
        results = {}
        
        # Process workspaces in batches to avoid overwhelming the API
        for i in range(0, len(workspace_ids), max_concurrent):
            batch = workspace_ids[i:i + max_concurrent]
            
            for workspace_id in batch:
                results[workspace_id] = self.stop_workspace(workspace_id, reason)
                time.sleep(0.5)  # Small delay between requests
            
            # Longer delay between batches
            if i + max_concurrent < len(workspace_ids):
                time.sleep(2)
        
        return results
    
    def get_workspace_status(self, workspace_id: str) -> Optional[Dict]:
        """
        Get current status of a specific workspace
        
        Args:
            workspace_id: Workspace ID to check
            
        Returns:
            Workspace status dictionary or None if not found
        """
        try:
            endpoint = f"/api/v2/workspaces/{workspace_id}"
            response = self._make_request('GET', endpoint)
            return response
            
        except Exception as e:
            print(f"Error getting workspace status for {workspace_id}: {e}")
            return None
    
    def get_templates(self) -> List[Dict]:
        """
        Get all templates
        
        Returns:
            List of template dictionaries
        """
        try:
            response = self._make_request('GET', '/api/v2/templates')
            return response if isinstance(response, list) else []
            
        except Exception as e:
            print(f"Error fetching templates: {e}")
            return []
    
    def get_template_map(self) -> Dict[str, str]:
        """
        Get mapping of template ID to template name
        
        Returns:
            Dictionary mapping template_id to template_name
        """
        templates = self.get_templates()
        return {tpl['id']: tpl['name'] for tpl in templates}
    
    def workspace_summary(self, workspace: Dict) -> str:
        """
        Generate a human-readable summary of a workspace
        
        Args:
            workspace: Workspace dictionary
            
        Returns:
            Formatted workspace summary string
        """
        owner = workspace.get('owner_name', 'Unknown')
        name = workspace.get('name', 'Unknown')
        status = workspace.get('latest_build', {}).get('status', 'Unknown')
        template_id = workspace.get('template_id', 'Unknown')
        
        # Get template name if possible
        template_map = getattr(self, '_template_map', None)
        if not template_map:
            self._template_map = self.get_template_map()
            template_map = self._template_map
        
        template_name = template_map.get(template_id, template_id)
        
        return f"{owner}/{name} ({template_name}) - {status}"
    
    def get_enterprise_quiet_hours(self) -> Optional[Dict]:
        """
        Get enterprise quiet hours configuration
        
        Returns:
            Enterprise quiet hours configuration or None if not available
        """
        try:
            response = self._make_request('GET', '/api/v2/deployment/config')
            return response.get('config', {}).get('user_quiet_hours_schedule', None)
        except Exception as e:
            print(f"Error fetching enterprise quiet hours: {e}")
            return None
    
    def get_user_quiet_hours_schedule(self, username: str = None) -> Optional[Dict]:
        """
        Get user quiet hours schedule configuration
        
        Args:
            username: Username to get schedule for (defaults to current user)
            
        Returns:
            User quiet hours schedule or None if not available
        """
        try:
            if username:
                endpoint = f"/api/v2/users/{username}/quiet-hours"
            else:
                endpoint = "/api/v2/users/me/quiet-hours"
            
            response = self._make_request('GET', endpoint)
            return response
        except Exception as e:
            print(f"Error fetching user quiet hours schedule: {e}")
            return None
    
    def get_current_user(self) -> Optional[Dict]:
        """
        Get current user information
        
        Returns:
            Current user information or None if not available
        """
        try:
            response = self._make_request('GET', '/api/v2/users/me')
            return response
        except Exception as e:
            print(f"Error fetching current user: {e}")
            return None
    
    def get_deployment_config(self) -> Optional[Dict]:
        """
        Get deployment configuration (includes enterprise settings)
        
        Returns:
            Deployment configuration or None if not available
        """
        try:
            response = self._make_request('GET', '/api/v2/deployment/config')
            return response
        except Exception as e:
            print(f"Error fetching deployment config: {e}")
            return None
    
    def print_enterprise_quiet_hours(self) -> None:
        """
        Print comprehensive enterprise and user quiet hours information
        """
        print("=" * 80)
        print("ENTERPRISE QUIET HOURS CONFIGURATION")
        print("=" * 80)
        
        # Get current user info
        current_user = self.get_current_user()
        if current_user:
            print(f"Current User: {current_user.get('username', 'Unknown')} ({current_user.get('email', 'No email')})")
            print(f"User ID: {current_user.get('id', 'Unknown')}")
            roles = current_user.get('roles', [])
            if roles and isinstance(roles[0], dict):
                role_names = [role.get('name', 'Unknown') for role in roles]
                print(f"User Role: {', '.join(role_names)}")
            else:
                print(f"User Role: {', '.join(roles) if roles else 'No roles'}")
        else:
            print("Current User: Unable to fetch user information")
        
        print()
        
        # Get deployment configuration
        deployment_config = self.get_deployment_config()
        if deployment_config:
            config = deployment_config.get('config', {})
            
            # Check for enterprise quiet hours settings
            quiet_hours_config = config.get('user_quiet_hours_schedule', {})
            
            print("📋 ENTERPRISE QUIET HOURS POLICY:")
            print("-" * 50)
            
            if quiet_hours_config:
                print(f"Enabled: {quiet_hours_config.get('enabled', 'Not set')}")
                print(f"Default Schedule: {quiet_hours_config.get('default_schedule', 'Not set')}")
                print(f"Allow User Override: {quiet_hours_config.get('allow_user_custom', 'Not set')}")
                
                # Print default schedule details if available
                default_schedule = quiet_hours_config.get('default_schedule')
                if default_schedule and isinstance(default_schedule, dict):
                    print("\nDefault Schedule Details:")
                    print(f"  Start Time: {default_schedule.get('start_time', 'Not set')}")
                    print(f"  End Time: {default_schedule.get('end_time', 'Not set')}")
                    print(f"  Timezone: {default_schedule.get('timezone', 'Not set')}")
                    print(f"  Days: {default_schedule.get('days', 'Not set')}")
            else:
                print("No enterprise quiet hours policy configured")
            
            # Check for other relevant enterprise settings
            print("\n🏢 OTHER ENTERPRISE SETTINGS:")
            print("-" * 50)
            
            # Workspace settings
            workspace_settings = {
                'max_ttl': config.get('max_ttl_ms'),
                'default_ttl': config.get('default_ttl_ms'),
                'activity_bump': config.get('activity_bump_ms'),
                'failure_ttl': config.get('failure_ttl_ms')
            }
            
            for setting, value in workspace_settings.items():
                if value is not None:
                    if setting.endswith('_ttl') or setting == 'activity_bump':
                        # Convert milliseconds to human readable
                        hours = value / (1000 * 60 * 60)
                        print(f"  {setting.replace('_', ' ').title()}: {hours:.1f} hours ({value} ms)")
                    else:
                        print(f"  {setting.replace('_', ' ').title()}: {value}")
        else:
            print("❌ Unable to fetch enterprise deployment configuration")
        
        print()
        
        # Get user-specific quiet hours schedule
        user_schedule = self.get_user_quiet_hours_schedule()
        
        print("👤 USER QUIET HOURS SCHEDULE:")
        print("-" * 50)
        
        if user_schedule:
            print("UserQuietHoursScheduleResponse:")
            print(json.dumps(user_schedule, indent=2))
            
            # Parse and display in a more readable format
            schedule = user_schedule.get('schedule', {})
            if schedule:
                print("\nParsed Schedule:")
                print(f"  Start Time: {schedule.get('start_time', 'Not set')}")
                print(f"  End Time: {schedule.get('end_time', 'Not set')}")
                print(f"  Timezone: {schedule.get('timezone', 'Not set')}")
                print(f"  Days: {schedule.get('days', 'Not set')}")
                print(f"  Next Activation: {user_schedule.get('next', 'Not set')}")
                print(f"  Time Until Next: {user_schedule.get('time_until_next', 'Not set')}")
        else:
            print("No user-specific quiet hours schedule configured")
        
        print("\n" + "=" * 80)
    
    def get_organizations(self) -> List[Dict]:
        """
        Get all organizations
        
        Returns:
            List of organization dictionaries
        """
        try:
            response = self._make_request('GET', '/api/v2/organizations')
            return response if isinstance(response, list) else []
        except Exception as e:
            print(f"Error fetching organizations: {e}")
            return []
    
    def get_groups(self, organization_id: str = None) -> List[Dict]:
        """
        Get groups, optionally filtered by organization
        
        Args:
            organization_id: Optional organization ID to filter by
            
        Returns:
            List of group dictionaries
        """
        try:
            if organization_id:
                endpoint = f"/api/v2/organizations/{organization_id}/groups"
            else:
                endpoint = "/api/v2/groups"
            
            response = self._make_request('GET', endpoint)
            return response if isinstance(response, list) else []
        except Exception as e:
            print(f"Error fetching groups: {e}")
            return []
    
    def get_users(self, organization_id: str = None) -> List[Dict]:
        """
        Get users, optionally filtered by organization
        
        Args:
            organization_id: Optional organization ID to filter by
            
        Returns:
            List of user dictionaries
        """
        try:
            if organization_id:
                endpoint = f"/api/v2/organizations/{organization_id}/members"
            else:
                endpoint = "/api/v2/users"
            
            response = self._make_request('GET', endpoint)
            
            # Handle different response formats
            if isinstance(response, dict):
                return response.get('users', [])
            elif isinstance(response, list):
                return response
            else:
                return []
        except Exception as e:
            print(f"Error fetching users: {e}")
            return []
    
    def get_group_members(self, group_id: str) -> List[Dict]:
        """
        Get members of a specific group
        
        Args:
            group_id: Group ID
            
        Returns:
            List of user dictionaries in the group
        """
        try:
            endpoint = f"/api/v2/groups/{group_id}/members"
            response = self._make_request('GET', endpoint)
            return response if isinstance(response, list) else []
        except Exception as e:
            print(f"Error fetching group members for {group_id}: {e}")
            return []
    
    def get_user_organizations(self, user_id: str) -> List[Dict]:
        """
        Get organizations that a user belongs to
        
        Args:
            user_id: User ID
            
        Returns:
            List of organization dictionaries
        """
        try:
            # Get user details which should include organization info
            endpoint = f"/api/v2/users/{user_id}"
            response = self._make_request('GET', endpoint)
            
            # Extract organization IDs from user data
            org_ids = response.get('organization_ids', [])
            
            # Get full organization details
            organizations = []
            all_orgs = self.get_organizations()
            
            for org in all_orgs:
                if org.get('id') in org_ids:
                    organizations.append(org)
            
            return organizations
        except Exception as e:
            print(f"Error fetching user organizations for {user_id}: {e}")
            return []
    
    def get_user_groups(self, user_id: str) -> List[Dict]:
        """
        Get groups that a user belongs to
        
        Args:
            user_id: User ID
            
        Returns:
            List of group dictionaries
        """
        try:
            # This might need to be implemented differently depending on Coder API
            # For now, we'll check all groups and see which ones the user is in
            all_groups = self.get_groups()
            user_groups = []
            
            for group in all_groups:
                group_members = self.get_group_members(group.get('id', ''))
                for member in group_members:
                    if member.get('id') == user_id:
                        user_groups.append(group)
                        break
            
            return user_groups
        except Exception as e:
            print(f"Error fetching user groups for {user_id}: {e}")
            return []
    
    def validate_connection(self) -> bool:
        """
        Validate connection to Coder API
        
        Returns:
            True if connection is successful, False otherwise
        """
        try:
            self._make_request('GET', '/api/v2/workspaces')
            return True
        except Exception as e:
            print(f"Connection validation failed: {e}")
            return False

def main():
    """Example usage of WorkspaceController"""
    try:
        controller = WorkspaceController()
        
        if not controller.validate_connection():
            print("Failed to connect to Coder API")
            sys.exit(1)
        
        print("Connected to Coder API successfully")
        
        # Get running workspaces
        running = controller.get_running_workspaces()
        print(f"Found {len(running)} running workspaces:")
        
        for ws in running:
            print(f"  - {controller.workspace_summary(ws)}")
        
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()