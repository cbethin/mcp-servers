# Node.js Sandbox Terminal MCP Server

A secure MCP server that provides sandboxed terminal sessions with controlled folder access using Node.js and Docker. This server allows safe execution of commands in isolated environments with customizable access permissions.

## Features

- **Docker-based Isolation**: Each sandbox runs in its own Docker container
- **Controlled Folder Access**: Specify which directories the sandbox can access
- **Session Management**: Maintain multiple independent sandbox sessions
- **Command Filtering**: Built-in security to prevent dangerous commands
- **File Operations**: Read, write, and manage files within sandboxes
- **Change Tracking**: Track and review all modifications made in a sandbox
- **Resource Limits**: CPU, memory, and process limits for safe execution
- **TypeScript**: Fully typed implementation for better reliability

## Prerequisites

- Node.js 20+
- Docker
- npm or yarn

## Installation

1. Clone and navigate to the directory:
   ```bash
   cd node_sandbox_terminal
   ```

2. Install dependencies:
   ```bash
   npm install
   ```

3. Build the TypeScript code:
   ```bash
   npm run build
   ```

4. Run in development mode:
   ```bash
   npm run dev
   ```

## Usage with Claude Desktop

Add to your `claude_desktop_config.json`:

```json
{
  "node_sandbox_terminal": {
    "command": "node",
    "args": ["/path/to/node_sandbox_terminal/dist/index.js"]
  }
}
```

Or with Docker:

```json
{
  "node_sandbox_terminal": {
    "command": "docker",
    "args": [
      "run", "-i", "--rm",
      "-v", "/var/run/docker.sock:/var/run/docker.sock",
      "-v", "/path/to/workdir:/workdir",
      "node-sandbox-terminal"
    ]
  }
}
```

## Available Tools

### sandbox_create
Create a new sandbox session with optional access restrictions.

```typescript
sandbox_create({
  source_path: "/path/to/project",
  session_name: "my_sandbox",
  allowed_paths: ["/shared/resources", "/data/readonly"],
  exclude_patterns: ["node_modules/**", "*.log"]
})
```

### sandbox_execute
Execute commands within a sandbox session.

```typescript
sandbox_execute({
  session_name: "my_sandbox",
  command: "npm install",
  working_dir: "src",
  timeout: 60
})
```

### sandbox_list
List all active sandbox sessions.

```typescript
sandbox_list()
// Returns: [{name, source, created, size, active}]
```

### sandbox_read_file
Read a file from within a sandbox.

```typescript
sandbox_read_file({
  session_name: "my_sandbox",
  file_path: "package.json"
})
```

### sandbox_write_file
Write or modify a file within a sandbox.

```typescript
sandbox_write_file({
  session_name: "my_sandbox",
  file_path: "config.json",
  content: '{"debug": true}'
})
```

### sandbox_list_files
List files and directories within a sandbox.

```typescript
sandbox_list_files({
  session_name: "my_sandbox",
  path: "/src"
})
```

### sandbox_diff
Show all changes made within a sandbox.

```typescript
sandbox_diff({
  session_name: "my_sandbox"
})
// Returns: {added: [...], modified: [...], deleted: [...]}
```

### sandbox_reset
Reset a sandbox to its original state.

```typescript
sandbox_reset({
  session_name: "my_sandbox"
})
```

### sandbox_destroy
Remove a sandbox session and free resources.

```typescript
sandbox_destroy({
  session_name: "my_sandbox"
})
```

### sandbox_commit
Apply sandbox changes back to a target directory.

```typescript
sandbox_commit({
  session_name: "my_sandbox",
  target_path: "/path/to/apply/changes",
  preview_only: true
})
```

## Configuration

### Environment Variables

```bash
# Maximum concurrent sandboxes (default: 10)
MAX_SANDBOXES=10

# Command timeout in seconds (default: 30)
COMMAND_TIMEOUT=30

# Maximum sandbox size in MB (default: 1000)
MAX_SANDBOX_SIZE=1000

# Enable network access in sandboxes (default: false)
SANDBOX_NETWORK_ENABLED=false

# Storage location for sandboxes
SANDBOX_STORAGE_PATH=/tmp/node-mcp-sandboxes

# Additional allowed paths (comma-separated)
SANDBOX_ALLOWED_PATHS=/shared/data,/configs/readonly

# Resource limits
SANDBOX_MEMORY=1g
SANDBOX_CPU_QUOTA=50
SANDBOX_PIDS_LIMIT=100
```

## Security Features

### Command Filtering
- Blocks dangerous system commands (shutdown, reboot, etc.)
- Prevents fork bombs and resource exhaustion attacks
- Filters privilege escalation attempts
- Blocks network attacks when network is disabled

### Resource Limits
- Memory limit: 1GB per container (configurable)
- CPU quota: 50% (configurable)
- Process limit: 100 processes
- Command timeout: 30 seconds (configurable)

### Path Isolation
- Sandboxes cannot access host filesystem outside designated areas
- Allowed paths are mounted read-only by default
- Path traversal attempts are blocked

### User Isolation
- Commands run as non-root user inside containers
- No sudo or privilege escalation available
- Environment variables are sanitized

## Docker Build

To build the Docker image:

```bash
docker build -t node-sandbox-terminal .
```

Run with Docker:

```bash
docker run -i --rm \
  -v /var/run/docker.sock:/var/run/docker.sock \
  -v $(pwd)/workdir:/workdir \
  node-sandbox-terminal
```

Note: The Docker socket mount is required for creating nested containers.

## Development

### Project Structure

```
node_sandbox_terminal/
├── src/
│   ├── index.ts           # MCP server entry point
│   ├── types/
│   │   └── index.ts       # TypeScript type definitions
│   └── utils/
│       ├── sandbox-manager.ts    # Core sandbox orchestration
│       ├── docker-sandbox.ts     # Docker container management
│       ├── command-validator.ts  # Security command filtering
│       ├── file-tracker.ts       # File change tracking
│       └── session-store.ts      # Session persistence
├── package.json
├── tsconfig.json
├── Dockerfile
└── README.md
```

### Adding New Features

1. **New Tools**: Add tool definitions in `src/index.ts`
2. **Security Rules**: Update patterns in `command-validator.ts`
3. **Docker Config**: Modify container settings in `docker-sandbox.ts`
4. **Session Data**: Extend types in `src/types/index.ts`

### Testing

```bash
# Run TypeScript compiler in watch mode
npm run build -- --watch

# Run development server
npm run dev

# Test with MCP inspector
npx @modelcontextprotocol/inspector dist/index.js
```

## Troubleshooting

### "Cannot connect to Docker daemon"
- Ensure Docker is running
- Check Docker socket permissions
- On Linux, add user to docker group: `sudo usermod -aG docker $USER`

### "Maximum concurrent sandboxes reached"
- Destroy unused sandboxes with `sandbox_destroy`
- Increase `MAX_SANDBOXES` environment variable
- Check for orphaned containers: `docker ps -a`

### "Command timed out"
- Increase timeout in `sandbox_execute` call
- Check if command is waiting for input
- Verify command syntax

### Container build fails
- Ensure base Ubuntu image is accessible
- Check Docker disk space
- Verify network connectivity for package installation

## Example Workflows

### Safe Package Testing

```typescript
// Create sandbox from project
sandbox_create({
  source_path: "/projects/my-app",
  session_name: "test_deps"
})

// Try installing new dependencies
sandbox_execute({
  session_name: "test_deps",
  command: "npm install express@5"
})

// Run tests
sandbox_execute({
  session_name: "test_deps",
  command: "npm test"
})

// Check what changed
sandbox_diff({ session_name: "test_deps" })

// If satisfied, commit changes
sandbox_commit({
  session_name: "test_deps",
  target_path: "/projects/my-app"
})
```

### Configuration Testing

```typescript
// Create sandbox with access to shared configs
sandbox_create({
  source_path: "/app",
  session_name: "config_test",
  allowed_paths: ["/configs/shared"]
})

// Modify configuration
sandbox_write_file({
  session_name: "config_test",
  file_path: "config.json",
  content: '{"apiUrl": "https://test.api.com"}'
})

// Test with new config
sandbox_execute({
  session_name: "config_test",
  command: "npm run validate-config"
})
```

## License

MIT

## Contributing

1. Fork the repository
2. Create a feature branch
3. Implement changes with tests
4. Ensure TypeScript compilation succeeds
5. Submit a pull request

## Support

For issues or questions:
- Check the troubleshooting section
- Review security considerations
- Submit an issue on GitHub