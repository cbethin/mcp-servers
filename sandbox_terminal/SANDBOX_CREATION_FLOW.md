# Sandbox Creation Flow

## Overview

The current implementation creates sandboxes as **local directory copies** with optional Docker container isolation. Here's how it works:

## Step-by-Step Process

### 1. **User calls `sandbox_create(source_path, session_name)`**
   - Validates the source path exists and is a directory
   - Checks session name doesn't already exist
   - Checks sandbox limit hasn't been reached

### 2. **Session Store creates directory structure**
   ```
   /tmp/mcp-sandboxes/            (or custom storage path)
   └── session_name/
       ├── workspace/             (copy of source files)
       └── initial_snapshot.json  (file state tracking)
   ```

### 3. **File copying (Primary isolation mechanism)**
   - Uses `shutil.copytree()` to copy entire source directory
   - Creates an isolated copy at `/tmp/mcp-sandboxes/session_name/workspace/`
   - This is the **main sandbox isolation** - changes only affect the copy

### 4. **File tracking initialization**
   - `FileChangeTracker` captures initial state of all files
   - Saves snapshot for later diff comparison
   - Tracks added, modified, and deleted files

### 5. **Docker container (Optional, if available)**
   - If Docker is installed and running:
     - Creates a Docker container named `mcp-sandbox-{session_name}`
     - Mounts the workspace directory into the container
     - Sets resource limits (memory, CPU, PIDs)
   - If Docker is not available:
     - Falls back to subprocess execution in the copied directory

### 6. **Command execution**
   - **With Docker**: Commands run inside the container with mounted workspace
   - **Without Docker**: Commands run as subprocesses with:
     - Working directory set to sandbox workspace
     - Modified environment variables (HOME, PWD)
     - No additional isolation beyond directory separation

## Current Implementation Summary

**Primary isolation**: Directory copying
- ✅ Files are isolated (changes don't affect original)
- ✅ Easy to implement and understand
- ❌ No process isolation without Docker
- ❌ No network isolation without Docker
- ❌ Commands can still access system files outside sandbox

**With Docker enabled**:
- ✅ Full process isolation
- ✅ Resource limits (CPU, memory, PIDs)
- ✅ Network isolation (if configured)
- ✅ Can't access host filesystem outside mounted workspace

**Without Docker**:
- ⚠️ Commands run with full system access
- ⚠️ Only file changes are isolated to the sandbox copy
- ⚠️ No resource limits
- ⚠️ Relies on `CommandRunner` blocklist for safety

## Key Components

1. **SessionStore**: Manages sandbox metadata and directory structure
2. **SandboxManager**: Coordinates creation, file copying, and Docker setup
3. **FileChangeTracker**: Tracks file modifications for diff and commit
4. **DockerSandbox**: Handles Docker container lifecycle (optional)
5. **CommandRunner**: Validates commands against blocklist for safety

## Storage Location

Default: `/tmp/mcp-sandboxes/`
- Can be customized via `SANDBOX_STORAGE_PATH` environment variable
- Each sandbox gets its own subdirectory
- Sessions persist across server restarts (metadata in sessions.json)