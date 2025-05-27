# Sandbox Terminal MCP Server

A Model Context Protocol (MCP) server that provides secure, isolated terminal command execution within sandboxed directory sessions. This server allows LLMs to safely explore and manipulate file systems without affecting the host system.

## Features

- **Directory Sandboxing**: Create isolated copies of directories for safe experimentation
- **Session Management**: Maintain multiple independent sandbox sessions
- **Command Execution**: Run shell commands within sandbox environments
- **File System Operations**: Full access to read, write, and modify files within sandboxes
- **State Persistence**: Maintain command history and working directory per session
- **Safety Controls**: Prevent commands from affecting the host system outside sandboxes
- **Resource Limits**: CPU, memory, and time limits for command execution

## Use Cases

- **Code Testing**: Test build commands and scripts without affecting source files
- **Learning & Exploration**: Safely explore command-line tools and their effects
- **Automated Testing**: Run test suites in isolated environments
- **Configuration Testing**: Experiment with configuration changes safely
- **Build Process Development**: Test complex build pipelines iteratively

## Getting Started

### Prerequisites

- Python 3.12+
- Docker (for containerized sandboxing)
- [`uv`](https://github.com/astral-sh/uv) package manager

### Installation

1. Install uv if you haven't already:
   ```sh
   pip install uv
   ```

2. Create and activate virtual environment:
   ```sh
   uv venv
   source .venv/bin/activate
   ```

3. Install dependencies:
   ```sh
   uv sync
   ```

4. Run the dev server:
   ```sh
   mcp dev main.py
   ```

5. Install to Claude MCP configuration:
   ```sh
   mcp install main.py
   ```

## Running with Docker

### Build the Docker image:
```sh
docker build -t sandbox-terminal-server .
```

### Run the server:
```sh
docker run -i --rm --privileged sandbox-terminal-server
```

Note: The `--privileged` flag is required for creating nested containers for sandboxing.

### Run with local code mounted (for development):
```sh
docker run -i --rm --privileged --mount type=bind,src=$(pwd),dst=/app sandbox-terminal-server
```

## Claude Desktop Configuration

Add to your `claude_desktop_config.json`:

### Using local Python:
```json
{
  "sandbox_terminal": {
    "command": "mcp",
    "args": ["run", "main.py"],
    "cwd": "/path/to/sandbox_terminal"
  }
}
```

### Using Docker:
```json
{
  "sandbox_terminal": {
    "command": "docker",
    "args": [
      "run", "-i", "--rm", "--privileged",
      "--mount", "type=bind,src=/path/to/sandbox_terminal,dst=/app",
      "sandbox-terminal-server"
    ]
  }
}
```

## Available Tools

### 1. sandbox_create(source_path, session_name)
Create a new sandbox session from a source directory.

```python
sandbox_create("/path/to/project", "test_session")
```

### 2. sandbox_list()
List all active sandbox sessions.

```python
sandbox_list()
# Returns: [{"name": "test_session", "source": "/path/to/project", "created": "2024-01-15T10:00:00", "size": "15MB"}]
```

### 3. sandbox_execute(session_name, command, working_dir)
Execute a command within a sandbox session.

```python
sandbox_execute("test_session", "npm install")
sandbox_execute("test_session", "npm test", working_dir="src")
```

### 4. sandbox_read_file(session_name, file_path)
Read a file from within a sandbox.

```python
sandbox_read_file("test_session", "package.json")
```

### 5. sandbox_write_file(session_name, file_path, content)
Write or modify a file within a sandbox.

```python
sandbox_write_file("test_session", "config.json", '{"debug": true}')
```

### 6. sandbox_list_files(session_name, path)
List files and directories within a sandbox.

```python
sandbox_list_files("test_session", "/")
sandbox_list_files("test_session", "/src")
```

### 7. sandbox_diff(session_name)
Show all changes made within a sandbox compared to the original.

```python
sandbox_diff("test_session")
# Returns: {"added": [...], "modified": [...], "deleted": [...]}
```

### 8. sandbox_commit(session_name, target_path)
Apply sandbox changes back to a target directory (with confirmation).

```python
sandbox_commit("test_session", "/path/to/apply/changes")
```

### 9. sandbox_destroy(session_name)
Remove a sandbox session and free resources.

```python
sandbox_destroy("test_session")
```

### 10. sandbox_reset(session_name)
Reset a sandbox to its original state.

```python
sandbox_reset("test_session")
```

## Safety Features

### Command Restrictions
- Network access is disabled by default (can be enabled per session)
- System directories (/etc, /sys, /proc) are read-only
- Resource limits: 30s timeout, 1GB memory, 50% CPU

### Sandbox Isolation
- Each sandbox runs in its own Docker container
- No access to host file system outside the sandbox
- Process isolation prevents interference between sessions

### Audit Trail
- All commands are logged with timestamps
- File modifications are tracked
- Session history is maintained

## Example Workflows

### Testing a Build Process

```python
# Create sandbox from project
sandbox_create("/home/user/my-project", "build_test")

# Try different build configurations
sandbox_execute("build_test", "npm install")
sandbox_write_file("build_test", ".env", "NODE_ENV=production")
sandbox_execute("build_test", "npm run build")

# Check the results
sandbox_list_files("build_test", "dist")
sandbox_read_file("build_test", "dist/index.html")

# If happy with results, could commit back
sandbox_commit("build_test", "/home/user/my-project-built")
```

### Exploring Command Effects

```python
# Create sandbox for learning
sandbox_create("/tmp/learn", "bash_learning")

# Try various commands safely
sandbox_execute("bash_learning", "touch file1.txt file2.txt")
sandbox_execute("bash_learning", "ls -la")
sandbox_execute("bash_learning", "find . -name '*.txt' -exec echo {} \\;")
sandbox_execute("bash_learning", "grep -r 'pattern' .")

# See what changed
sandbox_diff("bash_learning")

# Clean up
sandbox_destroy("bash_learning")
```

### Configuration Testing

```python
# Test nginx configuration
sandbox_create("/etc/nginx", "nginx_test")
sandbox_write_file("nginx_test", "sites-enabled/new-site.conf", nginx_config)
sandbox_execute("nginx_test", "nginx -t")  # Test configuration
sandbox_diff("nginx_test")  # Review changes
```

## Architecture

```
sandbox_terminal/
├── main.py                 # Entry point
├── server.py              # MCP server with tools
├── utils/
│   ├── sandbox_manager.py # Core sandboxing logic
│   ├── docker_sandbox.py  # Docker container management
│   ├── file_tracker.py    # File change tracking
│   ├── command_runner.py  # Safe command execution
│   └── session_store.py   # Session persistence
├── requirements.txt       # Dependencies
├── pyproject.toml        # Project metadata
├── Dockerfile            # Docker configuration
└── config/
    └── sandbox_config.yaml # Default sandbox settings
```

## Configuration

### Environment Variables

```sh
# Maximum number of concurrent sandboxes
export MAX_SANDBOXES=10

# Default timeout for commands (seconds)
export COMMAND_TIMEOUT=30

# Maximum sandbox size (MB)
export MAX_SANDBOX_SIZE=1000

# Enable network access in sandboxes
export SANDBOX_NETWORK_ENABLED=false

# Sandbox storage location
export SANDBOX_STORAGE_PATH=/tmp/mcp-sandboxes
```

### Configuration File

Create `config/sandbox_config.yaml`:

```yaml
sandbox:
  max_concurrent: 10
  default_timeout: 30
  max_size_mb: 1000
  
resource_limits:
  memory: "1g"
  cpu: "0.5"
  pids: 100
  
security:
  network_enabled: false
  readonly_paths:
    - /etc
    - /sys
    - /proc
  blocked_commands:
    - rm -rf /
    - shutdown
    - reboot
```

## Troubleshooting

### "Permission denied" errors
- Ensure Docker is running with proper permissions
- Check that the `--privileged` flag is used when running in Docker

### Sandbox creation fails
- Verify source directory exists and is readable
- Check available disk space
- Ensure Docker daemon is running

### Commands timeout
- Increase timeout with environment variable
- Check if command is waiting for input
- Consider breaking into smaller commands

## Security Considerations

1. **Host System Protection**: Sandboxes cannot access the host file system
2. **Resource Exhaustion**: Limits prevent runaway processes
3. **Network Isolation**: Disabled by default to prevent external access
4. **Command Filtering**: Dangerous commands are blocked
5. **Audit Logging**: All actions are logged for review

## Contributing

1. Fork the repository
2. Create a feature branch
3. Implement your changes with tests
4. Ensure security measures are maintained
5. Submit a pull request

## License

MIT License

## Support

For issues or questions:
- Review the security considerations
- Check the troubleshooting section
- Submit an issue on GitHub with logs