"""
Track file changes within sandbox sessions.
"""

import os
import hashlib
import json
from pathlib import Path
from typing import Dict, List, Set, Tuple, Optional
from dataclasses import dataclass, asdict
import logging

logger = logging.getLogger("sandbox_terminal.file_tracker")


@dataclass
class FileInfo:
    """Information about a file."""
    path: str
    size: int
    mode: int
    content_hash: str
    is_directory: bool
    
    def to_dict(self) -> dict:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: dict) -> "FileInfo":
        return cls(**data)


class FileChangeTracker:
    """Tracks file changes in a directory."""
    
    def __init__(self, base_path: str):
        self.base_path = Path(base_path)
        self.original_state: Dict[str, FileInfo] = {}
        self.ignored_patterns = {
            ".git", "__pycache__", "node_modules", 
            ".DS_Store", "*.pyc", "*.pyo"
        }
        
    def snapshot_directory(self, path: Optional[str] = None) -> Dict[str, FileInfo]:
        """Create a snapshot of all files in the directory."""
        target_path = Path(path) if path else self.base_path
        if not target_path.exists():
            return {}
            
        snapshot = {}
        
        for file_path in self._walk_directory(target_path):
            try:
                relative_path = file_path.relative_to(self.base_path)
                file_info = self._get_file_info(file_path)
                snapshot[str(relative_path)] = file_info
            except Exception as e:
                logger.warning(f"Failed to snapshot {file_path}: {e}")
                
        return snapshot
    
    def capture_initial_state(self) -> None:
        """Capture the initial state of the directory."""
        self.original_state = self.snapshot_directory()
        logger.info(f"Captured initial state: {len(self.original_state)} files")
        
    def get_changes(self) -> Dict[str, List[str]]:
        """Get all changes compared to the original state."""
        current_state = self.snapshot_directory()
        
        original_paths = set(self.original_state.keys())
        current_paths = set(current_state.keys())
        
        added = sorted(current_paths - original_paths)
        deleted = sorted(original_paths - current_paths)
        
        # Check for modifications
        modified = []
        for path in original_paths & current_paths:
            if self._is_modified(self.original_state[path], current_state[path]):
                modified.append(path)
        
        return {
            "added": added,
            "modified": sorted(modified),
            "deleted": deleted
        }
    
    def get_diff_summary(self) -> str:
        """Get a human-readable summary of changes."""
        changes = self.get_changes()
        
        total_changes = len(changes["added"]) + len(changes["modified"]) + len(changes["deleted"])
        
        if total_changes == 0:
            return "No changes detected"
            
        summary_parts = []
        if changes["added"]:
            summary_parts.append(f"{len(changes['added'])} added")
        if changes["modified"]:
            summary_parts.append(f"{len(changes['modified'])} modified")
        if changes["deleted"]:
            summary_parts.append(f"{len(changes['deleted'])} deleted")
            
        return f"{total_changes} files changed: {', '.join(summary_parts)}"
    
    def save_snapshot(self, file_path: str) -> None:
        """Save the current snapshot to a file."""
        snapshot = self.snapshot_directory()
        data = {
            "base_path": str(self.base_path),
            "timestamp": os.path.getmtime(self.base_path),
            "files": {
                path: info.to_dict() 
                for path, info in snapshot.items()
            }
        }
        
        with open(file_path, 'w') as f:
            json.dump(data, f, indent=2)
            
    def load_snapshot(self, file_path: str) -> None:
        """Load a snapshot from a file."""
        with open(file_path, 'r') as f:
            data = json.load(f)
            
        self.original_state = {
            path: FileInfo.from_dict(info)
            for path, info in data["files"].items()
        }
        
    def get_file_content_diff(self, file_path: str) -> Optional[Tuple[str, str]]:
        """Get the content difference for a specific file."""
        if file_path not in self.original_state:
            # New file
            full_path = self.base_path / file_path
            if full_path.exists() and full_path.is_file():
                try:
                    return "", full_path.read_text()
                except:
                    return None
            return None
            
        original_info = self.original_state[file_path]
        current_path = self.base_path / file_path
        
        if not current_path.exists():
            # Deleted file - would need to store content for this
            return None
            
        if current_path.is_file():
            try:
                current_content = current_path.read_text()
                # For now, return None for original content of modified files
                # In a full implementation, we'd store original content
                return None
            except:
                return None
                
        return None
    
    def _walk_directory(self, path: Path) -> List[Path]:
        """Walk directory and return all files, respecting ignore patterns."""
        files = []
        
        for item in path.rglob("*"):
            # Skip ignored patterns
            if any(pattern in str(item) for pattern in self.ignored_patterns):
                continue
                
            files.append(item)
            
        return files
    
    def _get_file_info(self, path: Path) -> FileInfo:
        """Get information about a file."""
        stat = path.stat()
        
        content_hash = ""
        if path.is_file() and stat.st_size < 10 * 1024 * 1024:  # Only hash files < 10MB
            try:
                content_hash = self._calculate_file_hash(path)
            except:
                content_hash = "error"
                
        return FileInfo(
            path=str(path),
            size=stat.st_size,
            mode=stat.st_mode,
            content_hash=content_hash,
            is_directory=path.is_dir()
        )
    
    def _calculate_file_hash(self, path: Path) -> str:
        """Calculate SHA256 hash of a file."""
        sha256_hash = hashlib.sha256()
        
        with open(path, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
                
        return sha256_hash.hexdigest()
    
    def _is_modified(self, original: FileInfo, current: FileInfo) -> bool:
        """Check if a file has been modified."""
        # For directories, check only mode changes
        if original.is_directory and current.is_directory:
            return original.mode != current.mode
            
        # For files, check size and content hash
        if not original.is_directory and not current.is_directory:
            if original.size != current.size:
                return True
            if original.content_hash and current.content_hash:
                return original.content_hash != current.content_hash
                
        # Type changed (file <-> directory)
        return original.is_directory != current.is_directory
    
    def reset_to_original(self) -> None:
        """Reset tracking to current state as original."""
        self.original_state = self.snapshot_directory()
        
    def get_total_size(self) -> int:
        """Get total size of all tracked files."""
        current_state = self.snapshot_directory()
        return sum(
            info.size 
            for info in current_state.values() 
            if not info.is_directory
        )
    
    def get_file_count(self) -> Tuple[int, int]:
        """Get count of files and directories."""
        current_state = self.snapshot_directory()
        files = sum(1 for info in current_state.values() if not info.is_directory)
        dirs = sum(1 for info in current_state.values() if info.is_directory)
        return files, dirs