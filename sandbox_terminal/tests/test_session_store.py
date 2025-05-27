"""
Unit tests for SessionStore
"""

import unittest
import tempfile
import shutil
import json
from pathlib import Path
from datetime import datetime

from utils.session_store import SessionStore, SessionMetadata


class TestSessionStore(unittest.TestCase):
    """Test cases for SessionStore."""
    
    def setUp(self):
        """Set up test environment."""
        self.test_dir = tempfile.mkdtemp(prefix="test_session_store_")
        self.store = SessionStore(self.test_dir)
        
    def tearDown(self):
        """Clean up test environment."""
        shutil.rmtree(self.test_dir, ignore_errors=True)
        
    def test_create_session(self):
        """Test creating a new session."""
        session = self.store.create_session("test1", "/path/to/source")
        
        self.assertEqual(session.session_id, "test1")
        self.assertEqual(session.source_path, "/path/to/source")
        self.assertIn("test1", self.store._sessions)
        
        # Check directory structure
        session_dir = Path(self.test_dir) / "test1"
        self.assertTrue(session_dir.exists())
        self.assertTrue((session_dir / "workspace").exists())
        self.assertTrue((session_dir / "metadata.json").exists())
        self.assertTrue((session_dir / "history.log").exists())
        self.assertTrue((session_dir / "changes.json").exists())
        
    def test_duplicate_session(self):
        """Test creating duplicate session fails."""
        self.store.create_session("test1", "/path/to/source")
        
        with self.assertRaises(ValueError) as context:
            self.store.create_session("test1", "/another/path")
        self.assertIn("already exists", str(context.exception))
        
    def test_get_session(self):
        """Test retrieving a session."""
        self.store.create_session("test1", "/path/to/source")
        
        session = self.store.get_session("test1")
        self.assertIsNotNone(session)
        self.assertEqual(session.session_id, "test1")
        
        # Non-existent session
        session = self.store.get_session("nonexistent")
        self.assertIsNone(session)
        
    def test_list_sessions(self):
        """Test listing all sessions."""
        sessions = self.store.list_sessions()
        self.assertEqual(len(sessions), 0)
        
        self.store.create_session("test1", "/path1")
        self.store.create_session("test2", "/path2")
        
        sessions = self.store.list_sessions()
        self.assertEqual(len(sessions), 2)
        session_ids = [s.session_id for s in sessions]
        self.assertIn("test1", session_ids)
        self.assertIn("test2", session_ids)
        
    def test_update_session(self):
        """Test updating session metadata."""
        session = self.store.create_session("test1", "/path/to/source")
        original_accessed = session.last_accessed
        
        # Modify session
        session.working_dir = "/workspace/src"
        session.environment["TEST_VAR"] = "test_value"
        
        self.store.update_session(session)
        
        # Retrieve and verify
        updated = self.store.get_session("test1")
        self.assertEqual(updated.working_dir, "/workspace/src")
        self.assertEqual(updated.environment["TEST_VAR"], "test_value")
        self.assertNotEqual(updated.last_accessed, original_accessed)
        
    def test_delete_session(self):
        """Test deleting a session."""
        self.store.create_session("test1", "/path/to/source")
        session_dir = Path(self.test_dir) / "test1"
        
        self.assertTrue(session_dir.exists())
        
        result = self.store.delete_session("test1")
        self.assertTrue(result)
        self.assertNotIn("test1", self.store._sessions)
        self.assertFalse(session_dir.exists())
        
        # Delete non-existent
        result = self.store.delete_session("nonexistent")
        self.assertFalse(result)
        
    def test_command_history(self):
        """Test adding commands to history."""
        self.store.create_session("test1", "/path/to/source")
        
        self.store.add_command_to_history(
            "test1",
            "ls -la",
            "file1.txt\nfile2.txt",
            0,
            0.5
        )
        
        session = self.store.get_session("test1")
        self.assertEqual(len(session.command_history), 1)
        
        cmd = session.command_history[0]
        self.assertEqual(cmd["command"], "ls -la")
        self.assertEqual(cmd["exit_code"], 0)
        self.assertEqual(cmd["execution_time"], 0.5)
        
        # Check history log
        history_file = Path(self.test_dir) / "test1" / "history.log"
        history_content = history_file.read_text()
        self.assertIn("ls -la", history_content)
        self.assertIn("Exit code: 0", history_content)
        
    def test_session_size(self):
        """Test getting session size."""
        self.store.create_session("test1", "/path/to/source")
        
        # Create some files
        workspace = Path(self.test_dir) / "test1" / "workspace"
        (workspace / "test.txt").write_text("Hello World!")
        (workspace / "subdir").mkdir()
        (workspace / "subdir" / "file.txt").write_text("More content")
        
        size = self.store.get_session_size("test1")
        self.assertGreater(size, 0)
        
        # Non-existent session
        size = self.store.get_session_size("nonexistent")
        self.assertEqual(size, 0)
        
    def test_persistence(self):
        """Test session persistence across instances."""
        # Create sessions
        self.store.create_session("test1", "/path1")
        self.store.create_session("test2", "/path2")
        
        session1 = self.store.get_session("test1")
        session1.working_dir = "/custom/dir"
        self.store.update_session(session1)
        
        # Create new store instance
        new_store = SessionStore(self.test_dir)
        
        # Verify sessions loaded
        sessions = new_store.list_sessions()
        self.assertEqual(len(sessions), 2)
        
        # Verify data preserved
        loaded_session = new_store.get_session("test1")
        self.assertEqual(loaded_session.working_dir, "/custom/dir")
        
    def test_cleanup_old_sessions(self):
        """Test cleaning up old sessions."""
        from datetime import datetime, timedelta
        
        # Create sessions
        session1 = self.store.create_session("test1", "/path1")
        session2 = self.store.create_session("test2", "/path2")
        
        # Make test1 old by directly modifying the stored session
        old_time = datetime.now() - timedelta(hours=25)
        self.store._sessions["test1"].last_accessed = old_time.isoformat()
        # Save to trigger persistence
        self.store._save_sessions()
        
        # Clean up sessions older than 24 hours
        removed = self.store.cleanup_old_sessions(max_age_hours=24)
        
        self.assertEqual(removed, 1)
        self.assertIsNone(self.store.get_session("test1"))
        self.assertIsNotNone(self.store.get_session("test2"))
        
    def test_session_metadata_serialization(self):
        """Test SessionMetadata serialization."""
        metadata = SessionMetadata("test1", "/source", "/sandbox")
        metadata.container_id = "container123"
        metadata.working_dir = "/workspace/src"
        metadata.environment = {"VAR": "value"}
        metadata.command_history = [{"command": "ls", "exit_code": 0}]
        
        # Convert to dict
        data = metadata.to_dict()
        self.assertEqual(data["session_id"], "test1")
        self.assertEqual(data["container_id"], "container123")
        self.assertEqual(data["environment"]["VAR"], "value")
        
        # Convert from dict
        loaded = SessionMetadata.from_dict(data)
        self.assertEqual(loaded.session_id, "test1")
        self.assertEqual(loaded.container_id, "container123")
        self.assertEqual(loaded.working_dir, "/workspace/src")
        self.assertEqual(loaded.environment["VAR"], "value")
        self.assertEqual(len(loaded.command_history), 1)


if __name__ == "__main__":
    unittest.main()