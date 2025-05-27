"""
Unit tests for SandboxManager
"""

import unittest
import tempfile
import shutil
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

from utils.sandbox_manager import SandboxManager
from utils.session_store import SessionMetadata


class TestSandboxManager(unittest.TestCase):
    """Test cases for SandboxManager."""
    
    def setUp(self):
        """Set up test environment."""
        self.storage_dir = tempfile.mkdtemp(prefix="test_sandbox_manager_")
        self.test_source = tempfile.mkdtemp(prefix="test_source_")
        
        # Create some test files
        Path(self.test_source, "file1.txt").write_text("Test content 1")
        Path(self.test_source, "file2.txt").write_text("Test content 2")
        Path(self.test_source, "subdir").mkdir()
        Path(self.test_source, "subdir", "file3.txt").write_text("Test content 3")
        
        # Mock Docker to avoid requiring Docker for tests
        with patch('utils.sandbox_manager.DOCKER_AVAILABLE', False):
            self.manager = SandboxManager(self.storage_dir)
            
    def tearDown(self):
        """Clean up test environment."""
        shutil.rmtree(self.storage_dir, ignore_errors=True)
        shutil.rmtree(self.test_source, ignore_errors=True)
        
    def test_create_sandbox_success(self):
        """Test successful sandbox creation."""
        result = self.manager.create_sandbox(self.test_source, "test_sandbox")
        
        self.assertTrue(result["success"])
        self.assertEqual(result["session_name"], "test_sandbox")
        self.assertEqual(result["source_path"], str(Path(self.test_source).resolve()))
        
        # Verify files were copied
        sandbox_path = Path(result["sandbox_path"])
        self.assertTrue(sandbox_path.exists())
        self.assertTrue((sandbox_path / "file1.txt").exists())
        self.assertTrue((sandbox_path / "subdir" / "file3.txt").exists())
        
        # Verify content matches
        content = (sandbox_path / "file1.txt").read_text()
        self.assertEqual(content, "Test content 1")
        
    def test_create_sandbox_invalid_source(self):
        """Test creating sandbox with invalid source."""
        with self.assertRaises(ValueError) as context:
            self.manager.create_sandbox("/nonexistent/path", "test")
        self.assertIn("does not exist", str(context.exception))
        
        # Test with file instead of directory
        temp_file = Path(self.test_source, "single_file.txt")
        temp_file.write_text("content")
        
        with self.assertRaises(ValueError) as context:
            self.manager.create_sandbox(str(temp_file), "test")
        self.assertIn("must be a directory", str(context.exception))
        
    def test_create_sandbox_duplicate_name(self):
        """Test creating sandbox with duplicate name."""
        self.manager.create_sandbox(self.test_source, "test_sandbox")
        
        with self.assertRaises(ValueError) as context:
            self.manager.create_sandbox(self.test_source, "test_sandbox")
        self.assertIn("already exists", str(context.exception))
        
    def test_sandbox_limit(self):
        """Test maximum sandbox limit."""
        # Set low limit for testing
        self.manager.max_sandboxes = 2
        
        # Create sandboxes up to limit
        self.manager.create_sandbox(self.test_source, "sandbox1")
        self.manager.create_sandbox(self.test_source, "sandbox2")
        
        # Try to exceed limit
        with self.assertRaises(ValueError) as context:
            self.manager.create_sandbox(self.test_source, "sandbox3")
        self.assertIn("Maximum number of sandboxes", str(context.exception))
        
    def test_destroy_sandbox(self):
        """Test destroying a sandbox."""
        self.manager.create_sandbox(self.test_source, "test_sandbox")
        
        # Verify it exists
        self.assertEqual(len(self.manager.list_sandboxes()), 1)
        
        # Destroy it
        result = self.manager.destroy_sandbox("test_sandbox")
        self.assertTrue(result["success"])
        
        # Verify it's gone
        self.assertEqual(len(self.manager.list_sandboxes()), 0)
        
        # Try to destroy non-existent
        with self.assertRaises(ValueError) as context:
            self.manager.destroy_sandbox("test_sandbox")
        self.assertIn("not found", str(context.exception))
        
    def test_list_sandboxes(self):
        """Test listing sandboxes."""
        # Empty list initially
        sandboxes = self.manager.list_sandboxes()
        self.assertEqual(len(sandboxes), 0)
        
        # Create some sandboxes
        self.manager.create_sandbox(self.test_source, "sandbox1")
        self.manager.create_sandbox(self.test_source, "sandbox2")
        
        sandboxes = self.manager.list_sandboxes()
        self.assertEqual(len(sandboxes), 2)
        
        # Check sandbox details
        names = [s["name"] for s in sandboxes]
        self.assertIn("sandbox1", names)
        self.assertIn("sandbox2", names)
        
        # Verify fields
        for sandbox in sandboxes:
            self.assertIn("name", sandbox)
            self.assertIn("source", sandbox)
            self.assertIn("created", sandbox)
            self.assertIn("size", sandbox)
            self.assertIn("status", sandbox)
            
    def test_execute_command_subprocess(self):
        """Test command execution with subprocess fallback."""
        self.manager.create_sandbox(self.test_source, "test_sandbox")
        
        # Execute simple command
        result = self.manager.execute_command("test_sandbox", "echo 'Hello World'")
        
        self.assertTrue(result["success"])
        self.assertEqual(result["exit_code"], 0)
        self.assertIn("Hello World", result["output"])
        
        # Execute command with working directory
        result = self.manager.execute_command("test_sandbox", "pwd", "subdir")
        self.assertTrue(result["success"])
        self.assertIn("subdir", result["output"])
        
    def test_execute_command_failure(self):
        """Test handling of failed commands."""
        self.manager.create_sandbox(self.test_source, "test_sandbox")
        
        # Execute failing command
        result = self.manager.execute_command("test_sandbox", "exit 1")
        
        self.assertFalse(result["success"])
        self.assertEqual(result["exit_code"], 1)
        
    def test_execute_command_invalid_session(self):
        """Test executing command with invalid session."""
        with self.assertRaises(ValueError) as context:
            self.manager.execute_command("nonexistent", "ls")
        self.assertIn("not found", str(context.exception))
        
    def test_execute_command_invalid_working_dir(self):
        """Test executing command with invalid working directory."""
        self.manager.create_sandbox(self.test_source, "test_sandbox")
        
        with self.assertRaises(ValueError) as context:
            self.manager.execute_command("test_sandbox", "ls", "nonexistent_dir")
        self.assertIn("does not exist", str(context.exception))
        
    def test_get_file_changes(self):
        """Test getting file changes."""
        self.manager.create_sandbox(self.test_source, "test_sandbox")
        session = self.manager.session_store.get_session("test_sandbox")
        
        # Initially no changes
        result = self.manager.get_file_changes("test_sandbox")
        self.assertTrue(result["success"])
        self.assertEqual(len(result["changes"]["added"]), 0)
        self.assertEqual(len(result["changes"]["modified"]), 0)
        self.assertEqual(len(result["changes"]["deleted"]), 0)
        
        # Make some changes
        sandbox_path = Path(session.sandbox_path)
        (sandbox_path / "new_file.txt").write_text("New content")
        (sandbox_path / "file1.txt").write_text("Modified content")
        (sandbox_path / "file2.txt").unlink()
        
        # Get changes
        result = self.manager.get_file_changes("test_sandbox")
        self.assertEqual(len(result["changes"]["added"]), 1)
        self.assertEqual(len(result["changes"]["modified"]), 1)
        self.assertEqual(len(result["changes"]["deleted"]), 1)
        self.assertIn("new_file.txt", result["changes"]["added"])
        self.assertIn("file1.txt", result["changes"]["modified"])
        self.assertIn("file2.txt", result["changes"]["deleted"])
        
    def test_reset_sandbox(self):
        """Test resetting sandbox to original state."""
        self.manager.create_sandbox(self.test_source, "test_sandbox")
        session = self.manager.session_store.get_session("test_sandbox")
        sandbox_path = Path(session.sandbox_path)
        
        # Make changes
        (sandbox_path / "new_file.txt").write_text("New")
        (sandbox_path / "file1.txt").write_text("Modified")
        (sandbox_path / "file2.txt").unlink()
        
        # Add command history
        self.manager.session_store.add_command_to_history(
            "test_sandbox", "echo test", "test", 0, 0.1
        )
        
        # Reset
        result = self.manager.reset_sandbox("test_sandbox")
        self.assertTrue(result["success"])
        
        # Verify files restored
        self.assertTrue((sandbox_path / "file1.txt").exists())
        self.assertTrue((sandbox_path / "file2.txt").exists())
        self.assertFalse((sandbox_path / "new_file.txt").exists())
        
        # Verify original content
        content = (sandbox_path / "file1.txt").read_text()
        self.assertEqual(content, "Test content 1")
        
        # Verify command history cleared
        session = self.manager.session_store.get_session("test_sandbox")
        self.assertEqual(len(session.command_history), 0)
        self.assertEqual(session.working_dir, "/")
        
    def test_copy_directory_overwrites(self):
        """Test that _copy_directory overwrites existing directories."""
        src = Path(self.test_source)
        dst = Path(self.storage_dir, "test_copy")
        
        # Create destination with different content
        dst.mkdir()
        (dst / "old_file.txt").write_text("Old content")
        
        # Copy should overwrite
        self.manager._copy_directory(src, str(dst))
        
        # Old file should be gone
        self.assertFalse((dst / "old_file.txt").exists())
        
        # New files should exist
        self.assertTrue((dst / "file1.txt").exists())
        
    def test_get_directory_size(self):
        """Test calculating directory size."""
        # Create files with known sizes
        test_dir = Path(self.storage_dir, "size_test")
        test_dir.mkdir()
        (test_dir / "file1.txt").write_text("12345")  # 5 bytes
        (test_dir / "file2.txt").write_text("1234567890")  # 10 bytes
        
        size = self.manager._get_directory_size(str(test_dir))
        self.assertEqual(size, 15)
        
    def test_sandbox_size_limit(self):
        """Test sandbox size limit enforcement."""
        # Set very low limit
        self.manager.max_sandbox_size = 100  # 100 bytes
        
        # Create large file in source
        large_content = "x" * 200
        Path(self.test_source, "large.txt").write_text(large_content)
        
        # Should fail due to size limit
        with self.assertRaises(ValueError) as context:
            self.manager.create_sandbox(self.test_source, "too_large")
        self.assertIn("exceeds limit", str(context.exception))
        
    def test_command_history_persistence(self):
        """Test that command history is persisted."""
        self.manager.create_sandbox(self.test_source, "test_sandbox")
        
        # Execute some commands
        self.manager.execute_command("test_sandbox", "echo 'test1'")
        self.manager.execute_command("test_sandbox", "echo 'test2'")
        
        # Get session and check history
        session = self.manager.session_store.get_session("test_sandbox")
        self.assertEqual(len(session.command_history), 2)
        self.assertEqual(session.command_history[0]["command"], "echo 'test1'")
        self.assertEqual(session.command_history[1]["command"], "echo 'test2'")
        
    @patch('utils.sandbox_manager.DockerSandbox')
    def test_docker_integration(self, mock_docker_class):
        """Test Docker integration when available."""
        # Create manager with mocked Docker
        with patch('utils.sandbox_manager.DOCKER_AVAILABLE', True):
            mock_docker = Mock()
            mock_docker_class.return_value = mock_docker
            
            # Mock container
            mock_container = Mock()
            mock_container.id = "container123"
            mock_docker.create_container.return_value = mock_container
            mock_docker.execute_command.return_value = ("output", 0)
            
            manager = SandboxManager(self.storage_dir)
            
            # Create sandbox
            result = manager.create_sandbox(self.test_source, "docker_test")
            self.assertTrue(result["success"])
            
            # Verify Docker methods called
            mock_docker.create_container.assert_called_once()
            mock_docker.start_container.assert_called_once_with(mock_container)
            
            # Execute command
            result = manager.execute_command("docker_test", "ls")
            self.assertTrue(result["success"])
            mock_docker.execute_command.assert_called_once()
            
    def test_working_directory_tracking(self):
        """Test that working directory is tracked across commands."""
        self.manager.create_sandbox(self.test_source, "test_sandbox")
        
        # Execute command with working directory
        self.manager.execute_command("test_sandbox", "pwd", "subdir")
        
        # Check that working directory was updated
        session = self.manager.session_store.get_session("test_sandbox")
        self.assertEqual(session.working_dir, "subdir")
        
    def test_absolute_path_normalization(self):
        """Test that absolute paths in working_dir are normalized."""
        self.manager.create_sandbox(self.test_source, "test_sandbox")
        
        # Execute with absolute path
        result = self.manager.execute_command("test_sandbox", "pwd", "/subdir")
        self.assertTrue(result["success"])
        
        # Should be normalized to relative
        session = self.manager.session_store.get_session("test_sandbox")
        self.assertEqual(session.working_dir, "subdir")


if __name__ == "__main__":
    unittest.main()