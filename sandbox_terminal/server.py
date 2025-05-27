"""
Sandbox Terminal MCP Server

Provides tools for secure command execution in isolated environments.
"""

import logging
from pathlib import Path
from typing import Dict, List, Optional, Any
from mcp.server.fastmcp import FastMCP

from utils.sandbox_manager import SandboxManager
from utils.command_runner import CommandRunner
from utils.docker_sandbox import DOCKER_AVAILABLE

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("sandbox_terminal_server")

# Create the MCP server instance
mcp = FastMCP(
    "sandbox_terminal_server",
    instructions="""
    This server provides secure, sandboxed terminal command execution.
    
    QUICK START:
    1. Create a sandbox from a directory: sandbox_create("/path/to/project", "my_sandbox")
    2. Execute commands: sandbox_execute("my_sandbox", "ls -la")
    3. Read/write files: sandbox_read_file("my_sandbox", "README.md")
    4. See changes: sandbox_diff("my_sandbox")
    5. Clean up: sandbox_destroy("my_sandbox")
    
    SAFETY FEATURES:
    - Commands run in isolated Docker containers
    - No access to host system outside sandbox
    - Resource limits prevent abuse
    - Network access disabled by default
    
    Perfect for testing builds, exploring commands, and safe experimentation!
    """
)

# Initialize the sandbox manager
sandbox_manager = SandboxManager()
command_runner = CommandRunner()

# ============================================================================
# TOOL 1: Create Sandbox
# ============================================================================

@mcp.async_tool()
async def sandbox_create(source_path: str, session_name: str, exclude: Optional[List[str]] = None):
    """
    Create a new sandbox session from a source directory.
    
    Creates an isolated copy of the specified directory where commands
    can be safely executed without affecting the original files.
    
    NOTE: First-time setup may take 2-3 minutes to build the Docker image
    with development tools (Python, Node.js, Git, etc.). Subsequent
    sandbox creation will be much faster.
    
    Args:
        source_path: Path to the source directory to sandbox
        session_name: Unique name for this sandbox session
        exclude: Optional list of glob patterns to exclude from sandbox
                (e.g., ["*.log", "node_modules/", "**/__pycache__"])
        
    Returns:
        Dict with session details or error message
        
    Example:
        sandbox_create("/home/user/my-project", "test_build")
        sandbox_create("/home/user", "home_sandbox", exclude=["Downloads/", "*.mp4"])
    """
    logger.info(f"Creating sandbox '{session_name}' from {source_path}")
    
    yield f"Starting sandbox creation for '{session_name}'..."
    
    try:
        # Check if this is the first sandbox (image might need building)
        if not hasattr(sandbox_create, '_image_built'):
            yield "First-time setup: Building Docker image (2-3 minutes)..."
            sandbox_create._image_built = True
            
        result = await sandbox_manager.create_sandbox_async(source_path, session_name, exclude)
        logger.info(f"Successfully created sandbox '{session_name}'")
        
        # Yield success information as strings
        yield f"✅ Sandbox '{session_name}' created successfully!"
        yield f"📁 Sandbox path: {result['sandbox_path']}"
        yield f"💾 Size: {result['size']}"
        yield f"🕐 Created at: {result['created_at']}"
    except Exception as e:
        logger.error(f"Failed to create sandbox: {e}")
        yield f"❌ Error creating sandbox: {str(e)}"

# ============================================================================
# TOOL 2: List Sandboxes
# ============================================================================

@mcp.tool()
def sandbox_list() -> List[Dict[str, Any]]:
    """
    List all active sandbox sessions.
    
    Returns information about each sandbox including its name,
    source directory, creation time, and current size.
    
    Returns:
        List of sandbox session details
    """
    logger.info("Listing all sandbox sessions")
    
    try:
        return sandbox_manager.list_sandboxes()
    except Exception as e:
        logger.error(f"Failed to list sandboxes: {e}")
        return []

# ============================================================================
# TOOL 3: Execute Command
# ============================================================================

@mcp.async_tool()
async def sandbox_execute(
    session_name: str, 
    command: str, 
    working_dir: Optional[str] = None
):
    """
    Execute a command within a sandbox session.
    
    Runs the specified command in the isolated sandbox environment.
    Commands have a 30-second timeout by default.
    
    Args:
        session_name: Name of the sandbox session
        command: Shell command to execute
        working_dir: Working directory (relative to sandbox root)
        
    Returns:
        Dict with command output, exit code, and execution details
        
    Example:
        sandbox_execute("my_sandbox", "npm install")
        sandbox_execute("my_sandbox", "python test.py", working_dir="tests")
    """
    logger.info(f"Executing in '{session_name}': {command}")
    
    yield f"Executing command: {command}"
    
    # Check command safety
    is_safe, reason = command_runner.is_command_safe(command)
    if not is_safe:
        yield f"❌ Command blocked: {reason}"
        return
    
    try:
        if working_dir:
            yield f"Working directory: {working_dir}"
            
        # Use the async version of execute_command
        result = await sandbox_manager.execute_command_async(
            session_name,
            command,
            working_dir
        )
        
        if result["success"]:
            yield f"✅ Command completed successfully ({result['execution_time']})"
            # Include key output lines
            output_lines = result["output"].strip().split('\n')
            if output_lines and output_lines[0]:
                for line in output_lines[:10]:  # Show first 10 lines
                    yield f"  {line}"
                if len(output_lines) > 10:
                    yield f"  ... ({len(output_lines) - 10} more lines)"
        else:
            yield f"❌ Command failed with exit code {result['exit_code']}"
            if result.get("output"):
                yield f"Error output: {result['output'][:200]}..."
    except Exception as e:
        logger.error(f"Failed to execute command: {e}")
        yield f"❌ Error: {str(e)}"

# ============================================================================
# TOOL 4: Read File
# ============================================================================

@mcp.tool()
def sandbox_read_file(session_name: str, file_path: str) -> Dict[str, Any]:
    """
    Read a file from within a sandbox.
    
    Retrieves the contents of a file from the sandbox session.
    File path is relative to the sandbox root.
    
    Args:
        session_name: Name of the sandbox session
        file_path: Path to the file (relative to sandbox root)
        
    Returns:
        Dict with file contents or error message
        
    Example:
        sandbox_read_file("my_sandbox", "package.json")
        sandbox_read_file("my_sandbox", "src/main.py")
    """
    logger.info(f"Reading file from '{session_name}': {file_path}")
    
    try:
        session = sandbox_manager.session_store.get_session(session_name)
        if not session:
            return {
                "success": False,
                "error": f"Session '{session_name}' not found"
            }
            
        # Ensure path is relative
        if file_path.startswith("/"):
            file_path = file_path.lstrip("/")
            
        full_path = Path(session.sandbox_path) / file_path
        
        if not full_path.exists():
            return {
                "success": False,
                "error": f"File not found: {file_path}"
            }
            
        if not full_path.is_file():
            return {
                "success": False,
                "error": f"Path is not a file: {file_path}"
            }
            
        # Check if file is within sandbox
        try:
            full_path.relative_to(session.sandbox_path)
        except ValueError:
            return {
                "success": False,
                "error": "Access denied: File is outside sandbox"
            }
            
        # Read file content
        content = full_path.read_text(encoding='utf-8', errors='replace')
        size = full_path.stat().st_size
        
        return {
            "success": True,
            "session_name": session_name,
            "file_path": file_path,
            "content": content,
            "size": f"{size / 1024:.1f}KB" if size > 1024 else f"{size}B"
        }
        
    except Exception as e:
        logger.error(f"Failed to read file: {e}")
        return {
            "success": False,
            "error": str(e)
        }

# ============================================================================
# TOOL 5: Write File
# ============================================================================

@mcp.tool()
def sandbox_write_file(
    session_name: str, 
    file_path: str, 
    content: str
) -> Dict[str, Any]:
    """
    Write or modify a file within a sandbox.
    
    Creates or overwrites a file in the sandbox session.
    Directories are created automatically if needed.
    
    Args:
        session_name: Name of the sandbox session
        file_path: Path to the file (relative to sandbox root)
        content: Content to write to the file
        
    Returns:
        Dict with write confirmation or error message
        
    Example:
        sandbox_write_file("my_sandbox", "config.json", '{"debug": true}')
    """
    logger.info(f"Writing file in '{session_name}': {file_path}")
    
    try:
        session = sandbox_manager.session_store.get_session(session_name)
        if not session:
            return {
                "success": False,
                "error": f"Session '{session_name}' not found"
            }
            
        # Ensure path is relative
        if file_path.startswith("/"):
            file_path = file_path.lstrip("/")
            
        full_path = Path(session.sandbox_path) / file_path
        
        # Check if path is within sandbox
        try:
            full_path.relative_to(session.sandbox_path)
        except ValueError:
            return {
                "success": False,
                "error": "Access denied: Path is outside sandbox"
            }
            
        # Create parent directories if needed
        full_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Write content
        full_path.write_text(content, encoding='utf-8')
        
        return {
            "success": True,
            "session_name": session_name,
            "file_path": file_path,
            "bytes_written": len(content.encode('utf-8'))
        }
        
    except Exception as e:
        logger.error(f"Failed to write file: {e}")
        return {
            "success": False,
            "error": str(e)
        }

# ============================================================================
# TOOL 6: List Files
# ============================================================================

@mcp.tool()
def sandbox_list_files(
    session_name: str, 
    path: str = "/"
) -> Dict[str, Any]:
    """
    List files and directories within a sandbox.
    
    Returns a directory listing for the specified path
    within the sandbox session.
    
    Args:
        session_name: Name of the sandbox session
        path: Directory path to list (default: root)
        
    Returns:
        Dict with file listing or error message
        
    Example:
        sandbox_list_files("my_sandbox")
        sandbox_list_files("my_sandbox", "/src")
    """
    logger.info(f"Listing files in '{session_name}': {path}")
    
    try:
        session = sandbox_manager.session_store.get_session(session_name)
        if not session:
            return {
                "success": False,
                "error": f"Session '{session_name}' not found"
            }
            
        # Ensure path is relative
        if path.startswith("/"):
            path = path.lstrip("/")
        if not path:
            path = "."
            
        full_path = Path(session.sandbox_path) / path
        
        if not full_path.exists():
            return {
                "success": False,
                "error": f"Path not found: {path}"
            }
            
        if not full_path.is_dir():
            return {
                "success": False,
                "error": f"Path is not a directory: {path}"
            }
            
        # Check if path is within sandbox
        try:
            full_path.relative_to(session.sandbox_path)
        except ValueError:
            return {
                "success": False,
                "error": "Access denied: Path is outside sandbox"
            }
            
        # List directory contents
        files = []
        for item in sorted(full_path.iterdir()):
            stat = item.stat()
            size = stat.st_size
            
            files.append({
                "name": item.name,
                "type": "directory" if item.is_dir() else "file",
                "size": f"{size / 1024:.1f}KB" if size > 1024 else f"{size}B"
            })
            
        return {
            "success": True,
            "session_name": session_name,
            "path": path,
            "files": files,
            "total_items": len(files)
        }
        
    except Exception as e:
        logger.error(f"Failed to list files: {e}")
        return {
            "success": False,
            "error": str(e)
        }

# ============================================================================
# TOOL 7: Show Differences
# ============================================================================

@mcp.tool()
def sandbox_diff(session_name: str) -> Dict[str, Any]:
    """
    Show all changes made within a sandbox compared to the original.
    
    Compares the current sandbox state with the original source
    directory to show what files have been added, modified, or deleted.
    
    Args:
        session_name: Name of the sandbox session
        
    Returns:
        Dict with lists of added, modified, and deleted files
        
    Example:
        sandbox_diff("my_sandbox")
    """
    logger.info(f"Getting diff for sandbox '{session_name}'")
    
    try:
        result = sandbox_manager.get_file_changes(session_name)
        return result
    except Exception as e:
        logger.error(f"Failed to get diff: {e}")
        return {
            "success": False,
            "error": str(e)
        }

# ============================================================================
# TOOL 8: Reset Sandbox
# ============================================================================

@mcp.tool()
def sandbox_reset(session_name: str) -> Dict[str, Any]:
    """
    Reset a sandbox to its original state.
    
    Discards all changes and restores the sandbox to match
    the original source directory.
    
    Args:
        session_name: Name of the sandbox session
        
    Returns:
        Dict with reset confirmation or error message
        
    Example:
        sandbox_reset("my_sandbox")
    """
    logger.info(f"Resetting sandbox '{session_name}'")
    
    try:
        result = sandbox_manager.reset_sandbox(session_name)
        logger.info(f"Successfully reset sandbox '{session_name}'")
        return result
    except Exception as e:
        logger.error(f"Failed to reset sandbox: {e}")
        return {
            "success": False,
            "error": str(e)
        }

# ============================================================================
# TOOL 9: Destroy Sandbox
# ============================================================================

@mcp.tool()
def sandbox_destroy(session_name: str) -> Dict[str, Any]:
    """
    Remove a sandbox session and free resources.
    
    Permanently deletes the sandbox and all its contents.
    This action cannot be undone.
    
    Args:
        session_name: Name of the sandbox session to destroy
        
    Returns:
        Dict with destruction confirmation or error message
        
    Example:
        sandbox_destroy("my_sandbox")
    """
    logger.info(f"Destroying sandbox '{session_name}'")
    
    try:
        result = sandbox_manager.destroy_sandbox(session_name)
        logger.info(f"Successfully destroyed sandbox '{session_name}'")
        return result
    except Exception as e:
        logger.error(f"Failed to destroy sandbox: {e}")
        return {
            "success": False,
            "error": str(e)
        }

# ============================================================================
# TOOL 10: Commit Changes (Advanced)
# ============================================================================

@mcp.tool()
def sandbox_commit(
    session_name: str, 
    target_path: str,
    confirm: bool = False
) -> Dict[str, Any]:
    """
    Apply sandbox changes back to a target directory.
    
    Copies the changes made in the sandbox to the specified target
    directory. Requires explicit confirmation to prevent accidents.
    
    Args:
        session_name: Name of the sandbox session
        target_path: Path where changes should be applied
        confirm: Must be True to actually apply changes
        
    Returns:
        Dict with commit details or error message
        
    Example:
        # First, see what would be changed
        sandbox_commit("my_sandbox", "/path/to/target", confirm=False)
        
        # Then, actually apply changes
        sandbox_commit("my_sandbox", "/path/to/target", confirm=True)
    """
    logger.info(f"Commit request for '{session_name}' to {target_path}")
    
    try:
        # Get the session
        session = sandbox_manager.session_store.get_session(session_name)
        if not session:
            return {
                "success": False,
                "error": f"Session '{session_name}' not found"
            }
        
        # Get file changes
        changes = sandbox_manager.get_file_changes(session_name)
        if not changes["success"]:
            return changes
        
        # Extract counts from the changes
        all_changes = changes["changes"]
        change_counts = {
            "added": len(all_changes["added"]),
            "modified": len(all_changes["modified"]),
            "deleted": len(all_changes["deleted"])
        }
        
        # Preview mode - show what would be changed
        if not confirm:
            return {
                "success": True,
                "mode": "preview",
                "message": "Preview mode - no changes applied",
                "would_change": change_counts,
                "files": all_changes,
                "source": session.sandbox_path,
                "target": target_path,
                "note": "Set confirm=True to apply changes"
            }
        
        # Validate target path
        target = Path(target_path).resolve()
        if not target.exists():
            return {
                "success": False,
                "error": f"Target path does not exist: {target_path}"
            }
        
        if not target.is_dir():
            return {
                "success": False,
                "error": f"Target path must be a directory: {target_path}"
            }
        
        # Apply changes
        import shutil
        sandbox_path = Path(session.sandbox_path)
        applied = {"added": 0, "modified": 0, "deleted": 0}
        errors = []
        
        # Apply added and modified files
        all_changes = changes["changes"]
        for file_path in all_changes["added"] + all_changes["modified"]:
            try:
                src = sandbox_path / file_path
                dst = target / file_path
                
                # Create parent directories if needed
                dst.parent.mkdir(parents=True, exist_ok=True)
                
                # Copy file
                shutil.copy2(src, dst)
                
                if file_path in all_changes["added"]:
                    applied["added"] += 1
                else:
                    applied["modified"] += 1
                    
            except Exception as e:
                errors.append(f"Failed to copy {file_path}: {str(e)}")
        
        # Apply deletions
        for file_path in all_changes["deleted"]:
            try:
                dst = target / file_path
                if dst.exists():
                    dst.unlink()
                    applied["deleted"] += 1
            except Exception as e:
                errors.append(f"Failed to delete {file_path}: {str(e)}")
        
        # Prepare result
        result = {
            "success": len(errors) == 0,
            "mode": "applied",
            "message": f"Changes from '{session_name}' applied to {target_path}",
            "changes_applied": applied,
            "source": session.sandbox_path,
            "target": str(target)
        }
        
        if errors:
            result["errors"] = errors
            result["partial_success"] = applied["added"] + applied["modified"] + applied["deleted"] > 0
            
        return result
        
    except Exception as e:
        logger.error(f"Failed to commit changes: {e}")
        return {
            "success": False,
            "error": str(e)
        }

# ============================================================================
# Resource: Server Status
# ============================================================================

@mcp.resource("sandbox-terminal://status")
def get_server_status() -> str:
    """Get current status of the sandbox terminal server."""
    try:
        # Get active sessions
        sessions = sandbox_manager.list_sandboxes()
        active_count = len(sessions)
        
        # Calculate total storage used
        total_size = 0
        for session in sessions:
            size_str = session.get("size", "0MB")
            # Parse size (format: "X.XMB")
            try:
                size_mb = float(size_str.replace("MB", ""))
                total_size += size_mb
            except:
                pass
        
        # Check Docker availability
        docker_status = "Available" if DOCKER_AVAILABLE else "Not available"
        if DOCKER_AVAILABLE and sandbox_manager.docker_sandbox:
            try:
                # Try to ping Docker
                import subprocess
                result = subprocess.run(["docker", "version"], capture_output=True, text=True)
                if result.returncode != 0:
                    docker_status = "Docker installed but not running"
            except:
                docker_status = "Docker command not found"
        
        # Get storage path
        storage_path = sandbox_manager.session_store.storage_path
        
        # Build status report
        status = f"""Sandbox Terminal Server Status
==============================
Status: Active
Docker: {docker_status}
Sessions: {active_count} active
Storage: {storage_path}
Total Size: {total_size:.1f}MB

Session Details:
"""
        
        # Add session details
        if sessions:
            for session in sessions:
                status += f"\n- {session['name']}"
                status += f"\n  Created: {session['created']}"
                status += f"\n  Size: {session['size']}"
                status += f"\n  Commands: {session['command_count']}"
                status += "\n"
        else:
            status += "\nNo active sessions\n"
            
        # Add limits
        status += f"""
Resource Limits:
- Max Sandboxes: {sandbox_manager.max_sandboxes}
- Max Sandbox Size: {sandbox_manager.max_sandbox_size / 1024 / 1024:.0f}MB
- Session Timeout: 24 hours
"""
        
        return status
        
    except Exception as e:
        logger.error(f"Failed to get server status: {e}")
        return f"Error getting server status: {str(e)}"

# Clean up old sessions on startup
try:
    sandbox_manager.session_store.cleanup_old_sessions(max_age_hours=24)
except Exception as e:
    logger.warning(f"Failed to cleanup old sessions: {e}")

# Export the server instance
if __name__ == "__main__":
    mcp.run()