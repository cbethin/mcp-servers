"""
Unit tests for CommandRunner
"""

import unittest
import os

from utils.command_runner import CommandRunner


class TestCommandRunner(unittest.TestCase):
    """Test cases for CommandRunner."""
    
    def setUp(self):
        """Set up test environment."""
        self.runner = CommandRunner()
        
    def test_safe_commands(self):
        """Test that safe commands are allowed."""
        safe_commands = [
            "ls -la",
            "echo 'Hello World'",
            "pwd",
            "cat file.txt",
            "npm install",
            "python script.py",
            "git status",
            "make build",
            "cd /workspace && ls"
        ]
        
        for cmd in safe_commands:
            is_safe, reason = self.runner.is_command_safe(cmd)
            self.assertTrue(is_safe, f"Command '{cmd}' should be safe but got: {reason}")
            
    def test_blocked_exact_commands(self):
        """Test that dangerous commands are blocked."""
        dangerous_commands = [
            "shutdown",
            "reboot",
            "poweroff",
            "halt",
            "rm -rf /",
            "rm -rf /*",
            "sudo rm -rf /",
            ":(){:|:&};:",  # Fork bomb
            "mkfs.ext4 /dev/sda",
            "dd if=/dev/zero of=/dev/sda"
        ]
        
        for cmd in dangerous_commands:
            is_safe, reason = self.runner.is_command_safe(cmd)
            self.assertFalse(is_safe, f"Command '{cmd}' should be blocked")
            self.assertIsNotNone(reason)
            
    def test_dangerous_patterns(self):
        """Test detection of dangerous patterns."""
        dangerous_patterns = [
            "echo test > /dev/sda",  # Writing to device
            "cat file > /dev/null",  # This should be safe
            "rm -rf / --no-preserve-root",
            "chmod 777 /",
            "sudo apt-get install",
            "su root",
            "echo 'test' >> /dev/random"
        ]
        
        for cmd in dangerous_patterns:
            is_safe, reason = self.runner.is_command_safe(cmd)
            if "/dev/null" in cmd:
                # /dev/null should be allowed
                self.assertTrue(is_safe)
            elif ">" in cmd and "/dev/" in cmd and "/dev/null" not in cmd:
                # Writing to other /dev files should be blocked
                self.assertFalse(is_safe)
                
    def test_parent_directory_traversal(self):
        """Test detection of excessive parent directory traversal."""
        # Normal traversal should be ok
        is_safe, _ = self.runner.is_command_safe("cd ../../src")
        self.assertTrue(is_safe)
        
        # Excessive traversal should be blocked
        is_safe, reason = self.runner.is_command_safe("cd ../../../../../../../../etc")
        self.assertFalse(is_safe)
        self.assertIn("parent directory", reason)
        
    def test_shell_bombs(self):
        """Test detection of potential shell bombs."""
        # Many pipes should be blocked
        is_safe, reason = self.runner.is_command_safe("cat /dev/urandom | grep a | grep b | grep c | grep d | grep e | grep f | grep g | grep h | grep i | grep j | grep k")
        self.assertFalse(is_safe)
        self.assertIn("shell bomb", reason)
        
        # Many background processes should be blocked
        is_safe, reason = self.runner.is_command_safe("sleep 1 & sleep 1 & sleep 1 & sleep 1 & sleep 1 & sleep 1 & sleep 1")
        self.assertFalse(is_safe)
        self.assertIn("shell bomb", reason)
        
        # Normal piping should be ok
        is_safe, _ = self.runner.is_command_safe("ls | grep txt | head -10")
        self.assertTrue(is_safe)
        
    def test_custom_blocked_commands(self):
        """Test custom blocked commands from environment."""
        # Set custom blocks
        os.environ["SANDBOX_BLOCKED_COMMANDS"] = "custom_danger,bad_command,risky"
        
        # Create new runner to load custom blocks
        runner = CommandRunner()
        
        is_safe, reason = runner.is_command_safe("custom_danger --force")
        self.assertFalse(is_safe)
        self.assertIn("custom_danger", reason)
        
        is_safe, reason = runner.is_command_safe("bad_command")
        self.assertFalse(is_safe)
        
        # Clean up
        del os.environ["SANDBOX_BLOCKED_COMMANDS"]
        
    def test_case_insensitive_blocking(self):
        """Test that blocking is case-insensitive."""
        dangerous_variations = [
            "SHUTDOWN",
            "Shutdown",
            "ShUtDoWn",
            "RM -RF /",
            "Rm -Rf /",
            "REBOOT"
        ]
        
        for cmd in dangerous_variations:
            is_safe, _ = self.runner.is_command_safe(cmd)
            self.assertFalse(is_safe, f"Command '{cmd}' should be blocked regardless of case")
            
    def test_sanitize_environment(self):
        """Test environment variable sanitization."""
        env = {
            "PATH": "/usr/bin:/bin",
            "HOME": "/home/user",
            "LD_PRELOAD": "/evil/library.so",
            "LD_LIBRARY_PATH": "/bad/path",
            "DYLD_INSERT_LIBRARIES": "/malicious.dylib",
            "SAFE_VAR": "safe_value"
        }
        
        sanitized = self.runner.sanitize_environment(env)
        
        # Safe vars should remain
        self.assertIn("PATH", sanitized)
        self.assertIn("HOME", sanitized)
        self.assertIn("SAFE_VAR", sanitized)
        
        # Dangerous vars should be removed
        self.assertNotIn("LD_PRELOAD", sanitized)
        self.assertNotIn("LD_LIBRARY_PATH", sanitized)
        self.assertNotIn("DYLD_INSERT_LIBRARIES", sanitized)
        
    def test_sanitize_environment_adds_path(self):
        """Test that PATH is added if missing."""
        env = {"HOME": "/home/user"}
        
        sanitized = self.runner.sanitize_environment(env)
        
        self.assertIn("PATH", sanitized)
        self.assertEqual(sanitized["PATH"], "/usr/local/bin:/usr/bin:/bin")
        
    def test_get_resource_limits(self):
        """Test resource limits configuration."""
        limits = self.runner.get_resource_limits()
        
        # Check all required limits are present
        self.assertIn("cpu_time", limits)
        self.assertIn("memory", limits)
        self.assertIn("processes", limits)
        self.assertIn("file_size", limits)
        self.assertIn("open_files", limits)
        
        # Check reasonable values
        self.assertGreater(limits["cpu_time"], 0)
        self.assertGreater(limits["memory"], 0)
        self.assertGreater(limits["processes"], 0)
        self.assertGreater(limits["file_size"], 0)
        self.assertGreater(limits["open_files"], 0)
        
    def test_whitespace_handling(self):
        """Test handling of commands with various whitespace."""
        commands = [
            "  shutdown  ",
            "\tshutdown\t",
            "\n\nshutdown\n\n",
            "shutdown\r\n"
        ]
        
        for cmd in commands:
            is_safe, _ = self.runner.is_command_safe(cmd)
            self.assertFalse(is_safe, f"Command with whitespace '{repr(cmd)}' should be blocked")
            
    def test_command_with_comments(self):
        """Test commands with comments."""
        # Comments should not bypass security
        is_safe, _ = self.runner.is_command_safe("echo safe # shutdown")
        self.assertTrue(is_safe)  # Comment should be ignored
        
        is_safe, _ = self.runner.is_command_safe("shutdown # just a comment")
        self.assertFalse(is_safe)  # Still dangerous
        
    def test_multiline_commands(self):
        """Test multiline command handling."""
        multiline_safe = """
        echo "Starting build"
        npm install
        npm test
        """
        is_safe, _ = self.runner.is_command_safe(multiline_safe)
        self.assertTrue(is_safe)
        
        multiline_dangerous = """
        echo "Starting"
        shutdown
        echo "Done"
        """
        is_safe, _ = self.runner.is_command_safe(multiline_dangerous)
        self.assertFalse(is_safe)


if __name__ == "__main__":
    unittest.main()