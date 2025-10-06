#!/usr/bin/env python3
"""
Enterprise Quiet Hours Checker - Display enterprise and user quiet hours configuration
Extends the coder-audit-simple project with enterprise quiet hours visibility
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone

# Import the workspace controller
from workspace_controller import WorkspaceController

def main():
    """Main function to display enterprise quiet hours information"""
    parser = argparse.ArgumentParser(description="Coder Enterprise Quiet Hours Checker")
    parser.add_argument("--json", action="store_true",
                       help="Output in JSON format")
    parser.add_argument("--user", 
                       help="Check quiet hours for specific user (requires admin privileges)")
    
    args = parser.parse_args()
    
    try:
        # Initialize controller
        controller = WorkspaceController()
        
        # Validate connection
        if not controller.validate_connection():
            print("Error: Could not connect to Coder API")
            sys.exit(1)
        
        if args.json:
            # Output in JSON format
            data = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "current_user": controller.get_current_user(),
                "enterprise_config": controller.get_deployment_config(),
                "user_quiet_hours": controller.get_user_quiet_hours_schedule(args.user)
            }
            print(json.dumps(data, indent=2))
        else:
            # Output in human-readable format
            controller.print_enterprise_quiet_hours()
            
            # If specific user requested, show their schedule too
            if args.user:
                print(f"\\n{'='*80}")
                print(f"USER QUIET HOURS FOR: {args.user}")
                print(f"{'='*80}")
                
                user_schedule = controller.get_user_quiet_hours_schedule(args.user)
                if user_schedule:
                    print("UserQuietHoursScheduleResponse:")
                    print(json.dumps(user_schedule, indent=2))
                else:
                    print(f"No quiet hours schedule found for user: {args.user}")
                
                print(f"{'='*80}")
    
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()