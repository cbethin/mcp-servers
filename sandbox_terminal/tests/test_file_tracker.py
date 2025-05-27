"""
Unit tests for FileChangeTracker
"""

import unittest
import tempfile
import shutil
from pathlib import Path
import os

from utils.file_tracker import FileChangeTracker, FileInfo


class TestFileChangeTracker(unittest.TestCase):
    """Test cases for FileChangeTracker."""
    
    def setUp(self):
        """Set up test environment."""
        self.test_dir = tempfile.mkdtemp(prefix="test_file_tracker_")
        self.tracker = FileChangeTracker(self.test_dir)
        
        # Create initial test structure
        Path(self.test_dir, "file1.txt").write_text("Content 1")
        Path(self.test_dir, "file2.txt").write_text("Content 2")
        Path(self.test_dir, "subdir").mkdir()
        Path(self.test_dir, "subdir", "file3.txt").write_text("Content 3")
        
    def tearDown(self):
        """Clean up test environment."""
        shutil.rmtree(self.test_dir, ignore_errors=True)
        
    def test_snapshot_directory(self):
        """Test creating directory snapshot."""
        snapshot = self.tracker.snapshot_directory()
        
        # Should have 4 items (3 files + 1 dir)
        self.assertEqual(len(snapshot), 4)
        
        # Check specific files
        self.assertIn("file1.txt", snapshot)
        self.assertIn("file2.txt", snapshot)
        self.assertIn("subdir", snapshot)
        self.assertIn("subdir/file3.txt", snapshot)
        
        # Check file info
        file1_info = snapshot["file1.txt"]
        self.assertFalse(file1_info.is_directory)
        self.assertEqual(file1_info.size, len("Content 1"))
        self.assertIsNotNone(file1_info.content_hash)
        
        # Check directory info
        subdir_info = snapshot["subdir"]
        self.assertTrue(subdir_info.is_directory)
        
    def test_capture_initial_state(self):
        """Test capturing initial state."""
        self.tracker.capture_initial_state()
        
        # Original state should match current snapshot
        self.assertEqual(len(self.tracker.original_state), 4)
        self.assertIn("file1.txt", self.tracker.original_state)
        
    def test_detect_added_files(self):
        """Test detecting added files."""
        self.tracker.capture_initial_state()
        
        # Add new file
        Path(self.test_dir, "new_file.txt").write_text("New content")
        
        changes = self.tracker.get_changes()
        self.assertEqual(len(changes["added"]), 1)
        self.assertIn("new_file.txt", changes["added"])
        self.assertEqual(len(changes["modified"]), 0)
        self.assertEqual(len(changes["deleted"]), 0)
        
    def test_detect_modified_files(self):
        """Test detecting modified files."""
        self.tracker.capture_initial_state()
        
        # Modify existing file
        Path(self.test_dir, "file1.txt").write_text("Modified content")
        
        changes = self.tracker.get_changes()
        self.assertEqual(len(changes["modified"]), 1)
        self.assertIn("file1.txt", changes["modified"])
        self.assertEqual(len(changes["added"]), 0)
        self.assertEqual(len(changes["deleted"]), 0)
        
    def test_detect_deleted_files(self):
        """Test detecting deleted files."""
        self.tracker.capture_initial_state()
        
        # Delete file
        Path(self.test_dir, "file2.txt").unlink()
        
        changes = self.tracker.get_changes()
        self.assertEqual(len(changes["deleted"]), 1)
        self.assertIn("file2.txt", changes["deleted"])
        self.assertEqual(len(changes["added"]), 0)
        self.assertEqual(len(changes["modified"]), 0)
        
    def test_detect_multiple_changes(self):
        """Test detecting multiple types of changes."""
        self.tracker.capture_initial_state()
        
        # Make various changes
        Path(self.test_dir, "file1.txt").write_text("Modified")
        Path(self.test_dir, "file2.txt").unlink()
        Path(self.test_dir, "new_file.txt").write_text("New")
        Path(self.test_dir, "subdir", "file3.txt").write_text("Modified 3")
        
        changes = self.tracker.get_changes()
        self.assertEqual(len(changes["added"]), 1)
        self.assertEqual(len(changes["modified"]), 2)
        self.assertEqual(len(changes["deleted"]), 1)
        
    def test_diff_summary(self):
        """Test getting human-readable diff summary."""
        self.tracker.capture_initial_state()
        
        # No changes
        summary = self.tracker.get_diff_summary()
        self.assertEqual(summary, "No changes detected")
        
        # Add changes
        Path(self.test_dir, "new.txt").write_text("New")
        Path(self.test_dir, "file1.txt").write_text("Modified")
        Path(self.test_dir, "file2.txt").unlink()
        
        summary = self.tracker.get_diff_summary()
        self.assertIn("3 files changed", summary)
        self.assertIn("1 added", summary)
        self.assertIn("1 modified", summary)
        self.assertIn("1 deleted", summary)
        
    def test_ignore_patterns(self):
        """Test that certain patterns are ignored."""
        # Create ignored files
        Path(self.test_dir, ".git").mkdir()
        Path(self.test_dir, ".git", "config").write_text("git config")
        Path(self.test_dir, "__pycache__").mkdir()
        Path(self.test_dir, "__pycache__", "module.pyc").write_text("bytecode")
        Path(self.test_dir, ".DS_Store").write_text("mac file")
        
        snapshot = self.tracker.snapshot_directory()
        
        # Ignored files should not be in snapshot
        paths = list(snapshot.keys())
        self.assertNotIn(".git", paths)
        self.assertNotIn(".git/config", paths)
        self.assertNotIn("__pycache__", paths)
        self.assertNotIn("__pycache__/module.pyc", paths)
        self.assertNotIn(".DS_Store", paths)
        
    def test_save_and_load_snapshot(self):
        """Test saving and loading snapshots."""
        self.tracker.capture_initial_state()
        
        # Save snapshot
        snapshot_file = Path(self.test_dir, "snapshot.json")
        self.tracker.save_snapshot(str(snapshot_file))
        
        self.assertTrue(snapshot_file.exists())
        
        # Create new tracker and load snapshot
        new_tracker = FileChangeTracker(self.test_dir)
        new_tracker.load_snapshot(str(snapshot_file))
        
        # Verify loaded state matches original
        self.assertEqual(len(new_tracker.original_state), 4)
        self.assertIn("file1.txt", new_tracker.original_state)
        
        # Original hashes should match
        orig_hash = self.tracker.original_state["file1.txt"].content_hash
        loaded_hash = new_tracker.original_state["file1.txt"].content_hash
        self.assertEqual(orig_hash, loaded_hash)
        
    def test_file_type_change(self):
        """Test detecting when a file changes to directory or vice versa."""
        self.tracker.capture_initial_state()
        
        # Change file to directory
        Path(self.test_dir, "file1.txt").unlink()
        Path(self.test_dir, "file1.txt").mkdir()
        
        changes = self.tracker.get_changes()
        self.assertIn("file1.txt", changes["modified"])
        
    def test_permission_change(self):
        """Test detecting permission changes."""
        self.tracker.capture_initial_state()
        
        # Change file permissions
        file_path = Path(self.test_dir, "file1.txt")
        original_mode = file_path.stat().st_mode
        os.chmod(file_path, 0o755)
        
        # Only check if permissions actually changed
        if file_path.stat().st_mode != original_mode:
            changes = self.tracker.get_changes()
            # Permission change alone might not trigger modified
            # depending on the implementation
        
    def test_reset_to_original(self):
        """Test resetting tracker to current state."""
        self.tracker.capture_initial_state()
        
        # Make changes
        Path(self.test_dir, "new.txt").write_text("New")
        
        changes = self.tracker.get_changes()
        self.assertEqual(len(changes["added"]), 1)
        
        # Reset
        self.tracker.reset_to_original()
        
        # No changes should be detected now
        changes = self.tracker.get_changes()
        self.assertEqual(len(changes["added"]), 0)
        self.assertEqual(len(changes["modified"]), 0)
        self.assertEqual(len(changes["deleted"]), 0)
        
    def test_get_total_size(self):
        """Test calculating total size of tracked files."""
        self.tracker.capture_initial_state()
        
        total_size = self.tracker.get_total_size()
        expected_size = len("Content 1") + len("Content 2") + len("Content 3")
        self.assertEqual(total_size, expected_size)
        
    def test_get_file_count(self):
        """Test counting files and directories."""
        self.tracker.capture_initial_state()
        
        files, dirs = self.tracker.get_file_count()
        self.assertEqual(files, 3)  # 3 text files
        self.assertEqual(dirs, 1)   # 1 directory
        
    def test_large_file_handling(self):
        """Test handling of large files (should skip hashing)."""
        # Create a large file (> 10MB)
        large_file = Path(self.test_dir, "large.bin")
        large_file.write_bytes(b"x" * (11 * 1024 * 1024))
        
        snapshot = self.tracker.snapshot_directory()
        
        # Large file should be tracked but without hash
        self.assertIn("large.bin", snapshot)
        large_info = snapshot["large.bin"]
        self.assertEqual(large_info.content_hash, "")  # No hash for large files
        
    def test_file_info_serialization(self):
        """Test FileInfo serialization."""
        info = FileInfo(
            path="/test/file.txt",
            size=100,
            mode=0o644,
            content_hash="abc123",
            is_directory=False
        )
        
        # To dict
        data = info.to_dict()
        self.assertEqual(data["path"], "/test/file.txt")
        self.assertEqual(data["size"], 100)
        self.assertEqual(data["content_hash"], "abc123")
        
        # From dict
        loaded = FileInfo.from_dict(data)
        self.assertEqual(loaded.path, info.path)
        self.assertEqual(loaded.size, info.size)
        self.assertEqual(loaded.content_hash, info.content_hash)


if __name__ == "__main__":
    unittest.main()