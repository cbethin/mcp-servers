"""
Session persistence and storage management for sandbox sessions.
"""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any
import logging

logger = logging.getLogger("sandbox_terminal.session_store")


class SessionMetadata:
    """Metadata for a sandbox session."""
    
    def __init__(self, session_id: str, source_path: str, sandbox_path: str):
        self.session_id = session_id
        self.source_path = source_path
        self.sandbox_path = sandbox_path
        self.created_at = datetime.now().isoformat()
        self.last_accessed = datetime.now().isoformat()
        self.container_id: Optional[str] = None
        self.working_dir = "/"
        self.command_history: List[Dict[str, Any]] = []
        self.environment: Dict[str, str] = {}
        self.status = "active"
        self.exclude_patterns: Optional[List[str]] = None
        
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "session_id": self.session_id,
            "source_path": self.source_path,
            "sandbox_path": self.sandbox_path,
            "created_at": self.created_at,
            "last_accessed": self.last_accessed,
            "container_id": self.container_id,
            "working_dir": self.working_dir,
            "command_history": self.command_history,
            "environment": self.environment,
            "status": self.status,
            "exclude_patterns": self.exclude_patterns
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SessionMetadata":
        """Create from dictionary."""
        session = cls(
            session_id=data["session_id"],
            source_path=data["source_path"],
            sandbox_path=data["sandbox_path"]
        )
        session.created_at = data.get("created_at", session.created_at)
        session.last_accessed = data.get("last_accessed", session.last_accessed)
        session.container_id = data.get("container_id")
        session.working_dir = data.get("working_dir", "/")
        session.command_history = data.get("command_history", [])
        session.environment = data.get("environment", {})
        session.status = data.get("status", "active")
        session.exclude_patterns = data.get("exclude_patterns")
        return session


class SessionStore:
    """Manages persistent storage of sandbox sessions."""
    
    def __init__(self, storage_path: Optional[str] = None):
        self.storage_path = Path(storage_path or os.environ.get(
            "SANDBOX_STORAGE_PATH", 
            "/tmp/mcp-sandboxes"
        ))
        self.storage_path.mkdir(parents=True, exist_ok=True)
        self.sessions_file = self.storage_path / "sessions.json"
        self._sessions: Dict[str, SessionMetadata] = {}
        self._load_sessions()
        
    def _load_sessions(self) -> None:
        """Load sessions from disk."""
        if self.sessions_file.exists():
            try:
                with open(self.sessions_file, 'r') as f:
                    data = json.load(f)
                    for session_data in data.get("sessions", []):
                        session = SessionMetadata.from_dict(session_data)
                        self._sessions[session.session_id] = session
                logger.info(f"Loaded {len(self._sessions)} sessions from disk")
            except Exception as e:
                logger.error(f"Failed to load sessions: {e}")
                self._sessions = {}
        
    def _save_sessions(self) -> None:
        """Save sessions to disk."""
        try:
            data = {
                "sessions": [
                    session.to_dict() 
                    for session in self._sessions.values()
                ],
                "last_updated": datetime.now().isoformat()
            }
            with open(self.sessions_file, 'w') as f:
                json.dump(data, f, indent=2)
            logger.debug(f"Saved {len(self._sessions)} sessions to disk")
        except Exception as e:
            logger.error(f"Failed to save sessions: {e}")
    
    def create_session(self, session_id: str, source_path: str) -> SessionMetadata:
        """Create a new session."""
        if session_id in self._sessions:
            raise ValueError(f"Session '{session_id}' already exists")
            
        sandbox_path = self.storage_path / session_id / "workspace"
        session = SessionMetadata(
            session_id=session_id,
            source_path=source_path,
            sandbox_path=str(sandbox_path)
        )
        
        # Create session directory structure
        session_dir = self.storage_path / session_id
        session_dir.mkdir(parents=True, exist_ok=True)
        (session_dir / "workspace").mkdir(exist_ok=True)
        (session_dir / "metadata.json").write_text(
            json.dumps(session.to_dict(), indent=2)
        )
        (session_dir / "history.log").touch()
        (session_dir / "changes.json").write_text(
            json.dumps({"added": [], "modified": [], "deleted": []})
        )
        
        self._sessions[session_id] = session
        self._save_sessions()
        logger.info(f"Created session '{session_id}' from {source_path}")
        return session
    
    def get_session(self, session_id: str) -> Optional[SessionMetadata]:
        """Get a session by ID."""
        session = self._sessions.get(session_id)
        if session:
            session.last_accessed = datetime.now().isoformat()
            self._save_sessions()
        return session
    
    def list_sessions(self) -> List[SessionMetadata]:
        """List all sessions."""
        return list(self._sessions.values())
    
    def update_session(self, session: SessionMetadata) -> None:
        """Update session metadata."""
        session.last_accessed = datetime.now().isoformat()
        self._sessions[session.session_id] = session
        
        # Also update the session-specific metadata file
        session_dir = self.storage_path / session.session_id
        metadata_file = session_dir / "metadata.json"
        if metadata_file.exists():
            metadata_file.write_text(
                json.dumps(session.to_dict(), indent=2)
            )
        
        self._save_sessions()
    
    def delete_session(self, session_id: str) -> bool:
        """Delete a session."""
        if session_id not in self._sessions:
            return False
            
        # Remove from memory
        del self._sessions[session_id]
        
        # Remove from disk
        session_dir = self.storage_path / session_id
        if session_dir.exists():
            import shutil
            shutil.rmtree(session_dir)
            
        self._save_sessions()
        logger.info(f"Deleted session '{session_id}'")
        return True
    
    def add_command_to_history(
        self, 
        session_id: str, 
        command: str,
        output: str,
        exit_code: int,
        execution_time: float
    ) -> None:
        """Add a command to session history."""
        session = self.get_session(session_id)
        if not session:
            return
            
        history_entry = {
            "command": command,
            "output": output[:1000],  # Truncate for storage
            "exit_code": exit_code,
            "execution_time": execution_time,
            "timestamp": datetime.now().isoformat()
        }
        
        session.command_history.append(history_entry)
        
        # Also append to history log file
        history_file = self.storage_path / session_id / "history.log"
        if history_file.exists():
            with open(history_file, 'a') as f:
                f.write(f"\n[{history_entry['timestamp']}] $ {command}\n")
                f.write(f"Exit code: {exit_code}, Time: {execution_time:.2f}s\n")
                if output:
                    f.write(f"Output:\n{output}\n")
                f.write("-" * 80 + "\n")
        
        self.update_session(session)
    
    def get_session_size(self, session_id: str) -> int:
        """Get the size of a session in bytes."""
        session_dir = self.storage_path / session_id
        if not session_dir.exists():
            return 0
            
        total_size = 0
        for path in session_dir.rglob("*"):
            if path.is_file():
                total_size += path.stat().st_size
        return total_size
    
    def cleanup_old_sessions(self, max_age_hours: int = 24) -> int:
        """Clean up sessions older than max_age_hours."""
        from datetime import datetime, timedelta
        
        now = datetime.now()
        sessions_to_delete = []
        
        for session_id, session in self._sessions.items():
            last_accessed = datetime.fromisoformat(session.last_accessed)
            if now - last_accessed > timedelta(hours=max_age_hours):
                sessions_to_delete.append(session_id)
        
        for session_id in sessions_to_delete:
            self.delete_session(session_id)
            
        return len(sessions_to_delete)