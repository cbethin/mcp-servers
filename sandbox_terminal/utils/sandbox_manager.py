"""
Core sandbox management logic that coordinates all components.
"""

import asyncio
import os
import shutil
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime

from .session_store import SessionStore, SessionMetadata
from .docker_sandbox import DockerSandbox, DOCKER_AVAILABLE
from .file_tracker import FileChangeTracker

logger = logging.getLogger("sandbox_terminal.sandbox_manager")


class SandboxManager:
    """Manages sandbox sessions and coordinates between components."""
    
    def __init__(self, storage_path: Optional[str] = None):
        self.session_store = SessionStore(storage_path)
        self.docker_sandbox = DockerSandbox() if DOCKER_AVAILABLE else None
        self.file_trackers: Dict[str, FileChangeTracker] = {}
        
        # Configuration
        self.max_sandboxes = int(os.environ.get("MAX_SANDBOXES", "10"))
        self.max_sandbox_size = int(os.environ.get("MAX_SANDBOX_SIZE", "1000")) * 1024 * 1024  # MB to bytes
        
        # Clean up any orphaned containers on startup
        if self.docker_sandbox:
            self._cleanup_orphaned_containers()
            
    def create_sandbox(self, source_path: str, session_name: str, exclude: Optional[List[str]] = None) -> Dict[str, Any]:
        """Create a new sandbox session."""
        # Validate inputs
        source_path = Path(source_path).resolve()
        if not source_path.exists():
            raise ValueError(f"Source path does not exist: {source_path}")
        if not source_path.is_dir():
            raise ValueError(f"Source path must be a directory: {source_path}")
            
        # Check session name
        if self.session_store.get_session(session_name):
            raise ValueError(f"Session '{session_name}' already exists")
            
        # Check sandbox limit
        active_sessions = [s for s in self.session_store.list_sessions() if s.status == "active"]
        if len(active_sessions) >= self.max_sandboxes:
            raise ValueError(f"Maximum number of sandboxes ({self.max_sandboxes}) reached")
            
        try:
            # Create session
            session = self.session_store.create_session(session_name, str(source_path))
            session.exclude_patterns = exclude
            self.session_store.update_session(session)
            
            # Copy files to sandbox
            logger.info(f"Copying files from {source_path} to {session.sandbox_path}")
            if exclude:
                logger.info(f"Excluding patterns: {exclude}")
            self._copy_directory(source_path, session.sandbox_path, exclude)
            
            # Check size limit
            sandbox_size = self._get_directory_size(session.sandbox_path)
            if sandbox_size > self.max_sandbox_size:
                # Clean up and fail
                self.session_store.delete_session(session_name)
                shutil.rmtree(session.sandbox_path, ignore_errors=True)
                raise ValueError(f"Sandbox size ({sandbox_size / 1024 / 1024:.1f}MB) exceeds limit ({self.max_sandbox_size / 1024 / 1024}MB)")
                
            # Initialize file tracker
            tracker = FileChangeTracker(session.sandbox_path)
            tracker.capture_initial_state()
            self.file_trackers[session_name] = tracker
            
            # Save initial snapshot
            snapshot_path = Path(session.sandbox_path).parent / "initial_snapshot.json"
            tracker.save_snapshot(str(snapshot_path))
            
            # Create Docker container if available
            if self.docker_sandbox:
                try:
                    container = self.docker_sandbox.create_container(
                        session_name,
                        session.sandbox_path,
                        session.environment
                    )
                    session.container_id = container.id
                    self.docker_sandbox.start_container(container)
                    self.session_store.update_session(session)
                except Exception as e:
                    logger.error(f"Failed to create Docker container: {e}")
                    # Continue without Docker
                    
            return {
                "success": True,
                "session_name": session_name,
                "source_path": str(source_path),
                "sandbox_path": session.sandbox_path,
                "size": f"{sandbox_size / 1024 / 1024:.1f}MB",
                "container_id": session.container_id,
                "created_at": session.created_at
            }
            
        except Exception as e:
            # Clean up on failure
            self.session_store.delete_session(session_name)
            if session_name in self.file_trackers:
                del self.file_trackers[session_name]
            raise
            
    def destroy_sandbox(self, session_name: str) -> Dict[str, Any]:
        """Destroy a sandbox session and clean up resources."""
        session = self.session_store.get_session(session_name)
        if not session:
            raise ValueError(f"Session '{session_name}' not found")
            
        # Stop and remove Docker container
        if self.docker_sandbox and session.container_id:
            try:
                container = self.docker_sandbox.get_container(session_name)
                if container:
                    self.docker_sandbox.stop_container(container)
                    self.docker_sandbox.remove_container(container)
            except Exception as e:
                logger.error(f"Failed to remove container: {e}")
                
        # Remove file tracker
        if session_name in self.file_trackers:
            del self.file_trackers[session_name]
            
        # Delete session (this also removes files)
        self.session_store.delete_session(session_name)
        
        return {
            "success": True,
            "message": f"Sandbox '{session_name}' destroyed successfully"
        }
        
    def list_sandboxes(self) -> List[Dict[str, Any]]:
        """List all sandbox sessions."""
        sessions = self.session_store.list_sessions()
        
        result = []
        for session in sessions:
            # Get size
            size = self.session_store.get_session_size(session.session_id)
            
            # Get container status
            container_status = "not_created"
            if self.docker_sandbox and session.container_id:
                container = self.docker_sandbox.get_container(session.session_id)
                if container:
                    container_status = container.status
                    
            result.append({
                "name": session.session_id,
                "source": session.source_path,
                "created": session.created_at,
                "last_accessed": session.last_accessed,
                "size": f"{size / 1024 / 1024:.1f}MB",
                "status": session.status,
                "container_status": container_status,
                "command_count": len(session.command_history)
            })
            
        return sorted(result, key=lambda x: x["last_accessed"], reverse=True)
        
    def execute_command(
        self,
        session_name: str,
        command: str,
        working_dir: Optional[str] = None,
        timeout: int = 30
    ) -> Dict[str, Any]:
        """Execute a command in a sandbox."""
        session = self.session_store.get_session(session_name)
        if not session:
            raise ValueError(f"Session '{session_name}' not found")
            
        # Validate working directory
        if working_dir:
            # Ensure it's relative and within sandbox
            if os.path.isabs(working_dir):
                working_dir = working_dir.lstrip("/")
            work_path = Path(session.sandbox_path) / working_dir
            if not work_path.exists():
                raise ValueError(f"Working directory does not exist: {working_dir}")
                
        # Update session working directory
        if working_dir:
            session.working_dir = working_dir
            self.session_store.update_session(session)
            
        # Execute command
        start_time = datetime.now()
        
        if self.docker_sandbox and session.container_id:
            # Execute in Docker container
            container = self.docker_sandbox.get_container(session_name)
            if not container:
                raise RuntimeError(f"Container not found for session '{session_name}'")
                
            output, exit_code = self.docker_sandbox.execute_command(
                container,
                command,
                working_dir=f"/workspace/{working_dir}" if working_dir else None,
                environment=session.environment,
                timeout=timeout
            )
        else:
            # Fallback to subprocess execution
            import subprocess
            
            # Build safe environment
            env = os.environ.copy()
            env.update(session.environment)
            env["HOME"] = session.sandbox_path
            env["PWD"] = str(Path(session.sandbox_path) / (working_dir or ""))
            
            try:
                proc = subprocess.run(
                    command,
                    shell=True,
                    cwd=Path(session.sandbox_path) / (working_dir or ""),
                    env=env,
                    capture_output=True,
                    text=True,
                    timeout=timeout
                )
                output = proc.stdout + proc.stderr
                exit_code = proc.returncode
            except subprocess.TimeoutExpired:
                output = "Command timed out"
                exit_code = -1
            except Exception as e:
                output = str(e)
                exit_code = -1
                
        execution_time = (datetime.now() - start_time).total_seconds()
        
        # Log to history
        self.session_store.add_command_to_history(
            session_name,
            command,
            output,
            exit_code,
            execution_time
        )
        
        return {
            "success": exit_code == 0,
            "session_name": session_name,
            "command": command,
            "working_dir": working_dir or session.working_dir,
            "output": output,
            "exit_code": exit_code,
            "execution_time": f"{execution_time:.2f}s"
        }
        
    async def execute_command_async(
        self,
        session_name: str,
        command: str,
        working_dir: Optional[str] = None,
        timeout: int = 30
    ) -> Dict[str, Any]:
        """Execute a command in a sandbox asynchronously."""
        # For now, just run the sync version in an executor
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            self.execute_command,
            session_name,
            command,
            working_dir,
            timeout
        )
        
    async def create_sandbox_async(
        self,
        source_path: str,
        session_name: str,
        exclude: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Create a new sandbox session asynchronously."""
        # Run the sync version in an executor to avoid blocking
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            self.create_sandbox,
            source_path,
            session_name,
            exclude
        )
        
    def get_file_changes(self, session_name: str) -> Dict[str, Any]:
        """Get file changes in a sandbox."""
        session = self.session_store.get_session(session_name)
        if not session:
            raise ValueError(f"Session '{session_name}' not found")
            
        tracker = self.file_trackers.get(session_name)
        if not tracker:
            # Recreate tracker if needed
            tracker = FileChangeTracker(session.sandbox_path)
            snapshot_path = Path(session.sandbox_path).parent / "initial_snapshot.json"
            if snapshot_path.exists():
                tracker.load_snapshot(str(snapshot_path))
            else:
                tracker.capture_initial_state()
            self.file_trackers[session_name] = tracker
            
        changes = tracker.get_changes()
        summary = tracker.get_diff_summary()
        
        return {
            "success": True,
            "session_name": session_name,
            "changes": changes,
            "summary": summary
        }
        
    def reset_sandbox(self, session_name: str) -> Dict[str, Any]:
        """Reset a sandbox to its original state."""
        session = self.session_store.get_session(session_name)
        if not session:
            raise ValueError(f"Session '{session_name}' not found")
            
        # Remove current workspace
        shutil.rmtree(session.sandbox_path, ignore_errors=True)
        
        # Copy original files again
        source_path = Path(session.source_path)
        # Use stored exclude patterns from session
        self._copy_directory(source_path, session.sandbox_path, session.exclude_patterns)
        
        # Reset file tracker
        if session_name in self.file_trackers:
            tracker = self.file_trackers[session_name]
            tracker.reset_to_original()
            
        # Clear command history
        session.command_history = []
        session.working_dir = "/"
        self.session_store.update_session(session)
        
        return {
            "success": True,
            "message": f"Sandbox '{session_name}' reset to original state"
        }
        
    def _copy_directory(self, src: Path, dst: str, exclude: Optional[List[str]] = None) -> None:
        """Copy a directory to sandbox location."""
        dst_path = Path(dst)
        
        # Remove destination if it exists
        if dst_path.exists():
            shutil.rmtree(dst_path)
            
        # Ensure parent directory exists
        dst_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Create ignore function if exclude patterns provided
        ignore_func = None
        if exclude:
            import fnmatch
            def ignore_patterns(directory, filenames):
                """Function to determine which files to ignore during copy."""
                ignored = set()
                
                # Calculate relative path of current directory from source
                try:
                    current_rel_path = Path(directory).relative_to(src)
                except ValueError:
                    current_rel_path = Path()
                
                for pattern in exclude:
                    # Handle directory patterns (ending with /)
                    if pattern.endswith('/'):
                        dir_pattern = pattern.rstrip('/')
                        # Check directory names
                        for name in filenames:
                            full_path = Path(directory) / name
                            if full_path.is_dir() and fnmatch.fnmatch(name, dir_pattern):
                                ignored.add(name)
                    else:
                        # Handle both files and directories for other patterns
                        for name in filenames:
                            full_path = Path(directory) / name
                            
                            # Build relative path from source
                            if current_rel_path == Path():
                                item_rel_path = name
                            else:
                                item_rel_path = str(current_rel_path / name)
                            
                            # Check against pattern
                            if '**' in pattern:
                                # Handle recursive patterns
                                # For directories, check if pattern matches directory structure
                                if full_path.is_dir():
                                    # Check if this directory or its contents would match
                                    # For example, **/__pycache__ should match any __pycache__ dir
                                    pattern_parts = pattern.split('/')
                                    if pattern_parts[0] == '**' and len(pattern_parts) > 1:
                                        # Pattern like **/__pycache__
                                        target_name = pattern_parts[1]
                                        if fnmatch.fnmatch(name, target_name):
                                            ignored.add(name)
                                else:
                                    # For files, use full relative path matching
                                    if fnmatch.fnmatch(item_rel_path, pattern):
                                        ignored.add(name)
                            else:
                                # Simple pattern matching
                                if fnmatch.fnmatch(name, pattern):
                                    ignored.add(name)
                                    
                return list(ignored)
            ignore_func = ignore_patterns
            
        # Use shutil for the copy
        shutil.copytree(src, dst, symlinks=True, ignore_dangling_symlinks=True, ignore=ignore_func)
        
    def _get_directory_size(self, path: str) -> int:
        """Get total size of a directory."""
        total_size = 0
        for dirpath, dirnames, filenames in os.walk(path):
            for filename in filenames:
                filepath = os.path.join(dirpath, filename)
                if os.path.exists(filepath):
                    total_size += os.path.getsize(filepath)
        return total_size
        
    def _cleanup_orphaned_containers(self) -> None:
        """Clean up any orphaned Docker containers."""
        if not self.docker_sandbox:
            return
            
        try:
            # Get all sandbox containers
            containers = self.docker_sandbox.list_sandbox_containers()
            
            # Get all active sessions
            active_sessions = {s.session_id for s in self.session_store.list_sessions()}
            
            # Remove containers for non-existent sessions
            for container in containers:
                session_name = container.name.replace("mcp-sandbox-", "")
                if session_name not in active_sessions:
                    logger.info(f"Removing orphaned container: {container.name}")
                    try:
                        container.remove(force=True)
                    except:
                        pass
                        
        except Exception as e:
            logger.error(f"Failed to cleanup orphaned containers: {e}")