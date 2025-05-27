"""
Test the async tool behavior with progress messages.
"""

import unittest
import tempfile
from pathlib import Path

from server import sandbox_create, sandbox_execute, sandbox_destroy
from tests.async_helper import sync_run_async_tool_with_progress


class TestAsyncToolBehavior(unittest.TestCase):
    """Test async tool progress messages and behavior."""
    
    def test_sandbox_create_progress_messages(self):
        """Test that sandbox_create yields appropriate progress messages."""
        with tempfile.TemporaryDirectory() as tmpdir:
            Path(tmpdir, "test.txt").write_text("Test content")
            
            # Get progress messages and result
            progress, result = sync_run_async_tool_with_progress(
                sandbox_create(tmpdir, "test_progress_sandbox")
            )
            
            # Check progress messages
            self.assertTrue(len(progress) >= 2)
            self.assertIn("Starting sandbox creation", progress[0])
            self.assertIn("created successfully", progress[-1])
            
            # Check result
            self.assertTrue(result["success"])
            self.assertEqual(result["session_name"], "test_progress_sandbox")
            
            # Clean up
            sandbox_destroy("test_progress_sandbox")
    
    def test_sandbox_create_first_time_message(self):
        """Test that first sandbox creation shows Docker build message."""
        # Reset the flag to simulate first run
        if hasattr(sandbox_create, '_image_built'):
            delattr(sandbox_create, '_image_built')
            
        with tempfile.TemporaryDirectory() as tmpdir:
            # Get progress messages
            progress, result = sync_run_async_tool_with_progress(
                sandbox_create(tmpdir, "test_first_time")
            )
            
            # Should have the first-time setup message
            docker_build_messages = [p for p in progress if "Docker image" in p]
            self.assertTrue(len(docker_build_messages) > 0)
            self.assertIn("2-3 minutes", docker_build_messages[0])
            
            # Clean up
            if result["success"]:
                sandbox_destroy("test_first_time")
    
    def test_sandbox_execute_progress_messages(self):
        """Test that sandbox_execute yields appropriate progress messages."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create sandbox first
            _, create_result = sync_run_async_tool_with_progress(
                sandbox_create(tmpdir, "test_exec_progress")
            )
            
            if create_result["success"]:
                # Test successful command
                progress, result = sync_run_async_tool_with_progress(
                    sandbox_execute("test_exec_progress", "echo 'Hello async'")
                )
                
                # Check progress messages
                self.assertTrue(len(progress) >= 2)
                self.assertIn("Executing command:", progress[0])
                self.assertIn("✓", progress[-1])  # Success checkmark
                self.assertIn("completed successfully", progress[-1])
                
                # Check result
                self.assertTrue(result["success"])
                self.assertIn("Hello async", result["output"])
                
                # Test failed command
                progress, result = sync_run_async_tool_with_progress(
                    sandbox_execute("test_exec_progress", "exit 42")
                )
                
                # Check failure message
                self.assertIn("✗", progress[-1])  # Failure X
                self.assertIn("exit code 42", progress[-1])
                self.assertFalse(result["success"])
                self.assertEqual(result["exit_code"], 42)
                
                # Test blocked command
                progress, result = sync_run_async_tool_with_progress(
                    sandbox_execute("test_exec_progress", "rm -rf /")
                )
                
                # Check blocked message
                blocked_messages = [p for p in progress if "blocked" in p.lower()]
                self.assertTrue(len(blocked_messages) > 0)
                self.assertFalse(result["success"])
                
                # Clean up
                sandbox_destroy("test_exec_progress")
    
    def test_sandbox_execute_with_working_dir(self):
        """Test that working directory is shown in progress."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create sandbox with subdirectory
            Path(tmpdir, "subdir").mkdir()
            Path(tmpdir, "subdir", "test.txt").write_text("In subdir")
            
            _, create_result = sync_run_async_tool_with_progress(
                sandbox_create(tmpdir, "test_workdir")
            )
            
            if create_result["success"]:
                # Execute with working directory
                progress, result = sync_run_async_tool_with_progress(
                    sandbox_execute("test_workdir", "pwd", working_dir="subdir")
                )
                
                # Check for working directory message
                workdir_messages = [p for p in progress if "Working directory:" in p]
                self.assertTrue(len(workdir_messages) > 0)
                self.assertIn("subdir", workdir_messages[0])
                
                # Clean up
                sandbox_destroy("test_workdir")


if __name__ == "__main__":
    unittest.main()