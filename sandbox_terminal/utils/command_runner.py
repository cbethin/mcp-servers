"""
Safe command execution with validation and filtering.
"""

import os
import re
import logging
from typing import List, Optional, Set

logger = logging.getLogger("sandbox_terminal.command_runner")


class CommandRunner:
    """Validates and filters commands for safe execution."""
    
    # Dangerous commands that should be blocked
    BLOCKED_COMMANDS = {
        "shutdown", "reboot", "poweroff", "halt",
        "init 0", "init 6", "systemctl poweroff",
        "rm -rf /", "rm -rf /*", "dd if=/dev/zero",
        "mkfs", "fdisk", "parted",
        ":(){:|:&};:",  # Fork bomb
    }
    
    # Dangerous patterns to check
    DANGEROUS_PATTERNS = [
        r">\s*/dev/(?!null)",  # Writing to device files (except /dev/null)
        r"rm\s+.*\s+/\s*$",  # Removing root
        r"chmod\s+777\s+/",  # Making root world-writable
        r"(?:sudo|su)\s+",  # Privilege escalation
    ]
    
    def __init__(self):
        self.custom_blocked = set()
        self.load_custom_blocks()
        
    def load_custom_blocks(self) -> None:
        """Load custom blocked commands from environment."""
        custom = os.environ.get("SANDBOX_BLOCKED_COMMANDS", "")
        if custom:
            self.custom_blocked = set(cmd.strip() for cmd in custom.split(","))
            
    def is_command_safe(self, command: str) -> tuple[bool, Optional[str]]:
        """Check if a command is safe to execute."""
        # Remove comments before checking
        command_parts = command.split('#')
        command_to_check = command_parts[0]
        command_lower = command_to_check.lower().strip()
        
        # Check exact matches
        for blocked in self.BLOCKED_COMMANDS | self.custom_blocked:
            if blocked in command_lower:
                return False, f"Command contains blocked pattern: {blocked}"
                
        # Check regex patterns
        for pattern in self.DANGEROUS_PATTERNS:
            if re.search(pattern, command_lower):
                return False, f"Command matches dangerous pattern"
                
        # Check for attempts to escape sandbox
        if "../" in command and command.count("../") > 3:
            return False, "Too many parent directory references"
            
        # Check for shell bombs
        if command.count("&") > 5 or command.count("|") > 10:
            return False, "Command appears to be a shell bomb"
            
        return True, None
        
    def sanitize_environment(self, env: dict) -> dict:
        """Sanitize environment variables."""
        # Remove potentially dangerous variables
        dangerous_vars = {"LD_PRELOAD", "LD_LIBRARY_PATH", "DYLD_INSERT_LIBRARIES"}
        
        sanitized = {
            k: v for k, v in env.items() 
            if k not in dangerous_vars
        }
        
        # Ensure safe PATH
        if "PATH" not in sanitized:
            sanitized["PATH"] = "/usr/local/bin:/usr/bin:/bin"
            
        return sanitized
        
    def get_resource_limits(self) -> dict:
        """Get resource limits for command execution."""
        return {
            "cpu_time": 30,  # seconds
            "memory": 1024 * 1024 * 1024,  # 1GB
            "processes": 100,
            "file_size": 100 * 1024 * 1024,  # 100MB
            "open_files": 256
        }