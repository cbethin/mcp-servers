# Sandbox Terminal MCP Server - Implementation Plan

## Overview

This document outlines the implementation plan for a secure MCP server that provides sandboxed terminal command execution. The server will allow LLMs to safely run commands on copies of directories without affecting the original files.

## Core Architecture

### 1. Sandboxing Strategy

**Primary Approach: Docker Containers**
- Each sandbox session runs in its own Docker container
- Containers are created from a minimal base image with necessary tools
- Volume mounts provide access to the sandboxed directory only
- Network isolation by default (can be enabled per session)

**Alternative Approach: Python subprocess + chroot (fallback)**
- For environments where Docker isn't available
- Uses Python's subprocess module with restricted environment
- Less isolation but still functional

### 2. Session Management

**Session Lifecycle:**
1. **Create**: Copy source directory to isolated location
2. **Execute**: Run commands within the sandbox
3. **Track**: Monitor file changes and command history
4. **Persist**: Save session state between commands
5. **Destroy**: Clean up resources when done

**Session Storage:**
```
/tmp/mcp-sandboxes/
├── sessions.json          # Session metadata
└── session_id/
    ├── workspace/         # Copied files
    ├── metadata.json      # Session info
    ├── history.log        # Command history
    └── changes.json       # File change tracking
```

### 3. Security Model

**Isolation Layers:**
1. **Container Isolation**: Separate Docker containers per session
2. **File System Isolation**: No access outside sandbox directory
3. **Resource Limits**: CPU, memory, and time constraints
4. **Command Filtering**: Block dangerous commands
5. **Network Isolation**: Disabled by default

**Threat Mitigation:**
- Fork bombs: Process limits (PIDs)
- Disk exhaustion: Size quotas
- CPU hogging: CPU shares limitation
- Memory leaks: Memory limits
- Network attacks: Network disabled
- Privilege escalation: Non-root container user

## Implementation Phases

### Phase 1: Core Infrastructure (Week 1)

**Tasks:**
1. Set up project structure
2. Implement basic session manager
3. Create Docker container orchestration
4. Build file copying mechanism
5. Develop session storage system

**Deliverables:**
- `utils/sandbox_manager.py`: Core session management
- `utils/docker_sandbox.py`: Docker container control
- `utils/session_store.py`: Session persistence
- Basic `server.py` with create/destroy tools

### Phase 2: Command Execution (Week 1-2)

**Tasks:**
1. Implement secure command runner
2. Add working directory support
3. Build output streaming
4. Create timeout mechanism
5. Add resource monitoring

**Deliverables:**
- `utils/command_runner.py`: Safe command execution
- `sandbox_execute` tool with full features
- Command history logging
- Real-time output streaming

### Phase 3: File Operations (Week 2)

**Tasks:**
1. Implement file reading within sandbox
2. Add file writing capabilities
3. Create directory listing tool
4. Build file change tracking
5. Develop diff generation

**Deliverables:**
- `utils/file_tracker.py`: Track file modifications
- File operation tools (read/write/list)
- `sandbox_diff` tool
- Change detection system

### Phase 4: Advanced Features (Week 3)

**Tasks:**
1. Implement sandbox reset functionality
2. Add commit mechanism (apply changes back)
3. Create snapshot/restore system
4. Build session import/export
5. Add multi-session management

**Deliverables:**
- `sandbox_reset` and `sandbox_commit` tools
- Snapshot functionality
- Session state import/export
- Concurrent session support

### Phase 5: Security & Polish (Week 3-4)

**Tasks:**
1. Implement command filtering
2. Add resource limit enforcement
3. Create audit logging
4. Build permission system
5. Add comprehensive error handling

**Deliverables:**
- Security configuration system
- Audit trail functionality
- Permission checks
- Robust error handling
- Performance optimizations

## Technical Implementation Details

### Docker Container Setup

```dockerfile
FROM ubuntu:22.04

# Install essential tools
RUN apt-get update && apt-get install -y \
    python3 python3-pip \
    nodejs npm \
    git curl wget \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN useradd -m -s /bin/bash sandbox

# Set up working directory
WORKDIR /workspace

# Switch to non-root user
USER sandbox

# Resource limits set at runtime
```

### Session Manager Architecture

```python
class SandboxSession:
    def __init__(self, session_id, source_path):
        self.session_id = session_id
        self.source_path = source_path
        self.container_id = None
        self.workspace_path = None
        self.created_at = datetime.now()
        self.command_history = []
        self.file_changes = FileChangeTracker()
        
    def execute_command(self, command, working_dir=None):
        # Validate command
        # Set up environment
        # Execute in container
        # Log results
        # Return output
        
    def get_file_changes(self):
        # Compare current state to original
        # Return diff
```

### Command Execution Flow

```python
def sandbox_execute(session_name: str, command: str, working_dir: Optional[str] = None):
    # 1. Validate session exists
    session = session_manager.get_session(session_name)
    if not session:
        return {"error": "Session not found"}
    
    # 2. Validate command safety
    if is_dangerous_command(command):
        return {"error": "Command blocked for security"}
    
    # 3. Prepare execution environment
    env = prepare_sandbox_environment(session)
    
    # 4. Execute with timeout
    result = docker_client.exec_create(
        session.container_id,
        command,
        workdir=working_dir or "/workspace",
        environment=env
    )
    
    # 5. Stream output
    output = docker_client.exec_start(result['Id'], stream=True)
    
    # 6. Log and return
    session.add_to_history(command, output)
    return {"output": output, "exit_code": exit_code}
```

### File Change Tracking

```python
class FileChangeTracker:
    def __init__(self, base_path):
        self.base_path = base_path
        self.original_state = self.snapshot_directory()
        
    def snapshot_directory(self):
        # Create hash of all files
        # Store metadata (size, permissions, content hash)
        
    def get_changes(self):
        current_state = self.snapshot_directory()
        # Compare with original_state
        # Return added, modified, deleted files
```

## Testing Strategy

### Unit Tests
- Session creation/destruction
- Command execution
- File operations
- Security filters
- Resource limits

### Integration Tests
- Full workflow tests
- Docker container lifecycle
- Multi-session handling
- Error recovery
- Performance under load

### Security Tests
- Attempt privilege escalation
- Try to access host system
- Test resource exhaustion
- Verify network isolation
- Check command filtering

## Performance Considerations

### Optimization Areas
1. **Container Reuse**: Pool pre-created containers
2. **Lazy Copying**: Copy-on-write for large directories
3. **Caching**: Cache unchanged files between sessions
4. **Streaming**: Stream command output instead of buffering
5. **Cleanup**: Automatic cleanup of old sessions

### Resource Management
- Maximum concurrent sessions: 10 (configurable)
- Per-session memory limit: 1GB
- Per-session CPU limit: 50%
- Command timeout: 30 seconds
- Maximum sandbox size: 1GB

## Error Handling

### Error Categories
1. **Session Errors**: Invalid session, session not found
2. **Resource Errors**: Out of memory, disk full
3. **Docker Errors**: Container failures, daemon issues
4. **Command Errors**: Timeout, non-zero exit
5. **Security Errors**: Blocked commands, permission denied

### Recovery Strategies
- Automatic container restart on failure
- Session state persistence for recovery
- Graceful degradation (fallback to subprocess)
- Clear error messages for users
- Automatic cleanup on errors

## Future Enhancements

### Version 2.0 Features
1. **Web IDE Integration**: Browser-based file editing
2. **Collaborative Sessions**: Multiple users in same sandbox
3. **Template System**: Pre-configured environments
4. **Plugin System**: Extend with custom tools
5. **Cloud Storage**: S3/GCS backend for sessions

### Potential Integrations
- Git integration for version control
- CI/CD pipeline testing
- Database sandboxing
- Network service simulation
- Performance profiling tools

## Dependencies

### Python Packages
```toml
[project]
dependencies = [
    "mcp[cli]>=1.6.0",
    "docker>=7.0.0",
    "watchdog>=3.0.0",  # File system monitoring
    "pyyaml>=6.0",      # Configuration
    "aiofiles>=23.0",   # Async file operations
    "psutil>=5.9",      # System resource monitoring
]
```

### System Requirements
- Docker Engine 24.0+
- Python 3.12+
- Linux or macOS (Windows via WSL2)
- 4GB RAM minimum
- 10GB free disk space

## Timeline

**Week 1**: Core infrastructure, basic session management
**Week 2**: Command execution, file operations
**Week 3**: Advanced features, security implementation
**Week 4**: Testing, documentation, optimization

Total estimated time: 4 weeks for full implementation