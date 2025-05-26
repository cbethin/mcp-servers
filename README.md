# MCP Servers Collection

A collection of Model Context Protocol (MCP) servers that enable Claude and other LLMs to interact with external systems through tool calls.

## Overview

This repository contains three MCP server implementations:

1. **Phillips Hue Server** (`phillips_hue_server/`) - Control Philips Hue smart lighting
2. **Task Server** (`todo_server/`) - Manage tasks with SQLite/SQLAlchemy storage  
3. **Template Server** (`template/`) - Base template for creating new MCP servers

## What is MCP?

The Model Context Protocol (MCP) is a standardized way for LLMs like Claude to interact with external systems through structured tool calls. MCP servers expose tools and resources that LLMs can use to perform actions and retrieve information.

## Quick Start

All servers follow the same setup process:

### Prerequisites

- Python 3.12+ 
- [`uv`](https://github.com/astral-sh/uv) package manager

### Installation

1. Install uv if you haven't already:
   ```sh
   pip install uv
   ```

2. Navigate to the server directory:
   ```sh
   cd phillips_hue_server  # or todo_server or template
   ```

3. Create and activate virtual environment:
   ```sh
   uv venv
   source .venv/bin/activate
   ```

4. Install dependencies:
   ```sh
   uv sync
   ```

5. Run in development mode:
   ```sh
   mcp dev main.py
   ```

6. Install to Claude MCP configuration:
   ```sh
   mcp install main.py
   ```

### Docker Support

All servers include Docker support:

```sh
# Build image
docker build -t [server-name] .

# Run server
docker run -i --rm [server-name]

# Run with local code mounted (development)
docker run -i --rm --mount type=bind,src=$(pwd),dst=/app [server-name]
```

## Server Descriptions

### Phillips Hue Server

Controls Philips Hue smart lighting systems with 12 powerful tools:

**Key Features:**
- Auto-discovery and setup of Hue bridges
- Natural language color control ("sunset", "warm white", etc.)
- Scene management (apply/save/manage scenes)
- Smooth light transitions
- Group management
- Comprehensive status reporting

**Tools:**
- `setup()` - Complete bridge discovery and setup
- `control()` - Universal light/group control with natural language
- `get_status()` - Get info about lights, groups, or bridges
- `scene()` - Apply Hue or custom scenes
- `transition()` - Smooth light transitions
- `save_scene()` - Save current lighting as scene
- `manage_scenes()` - List and manage scenes
- `bridge()` - Bridge management utilities
- `groups()` - Create and manage light groups
- `config()` - Configuration management
- `colors()` - Color utilities and suggestions
- `test()` - Test server functionality

**Environment Variables:**
```sh
export HUE_BRIDGE_IP="192.168.1.X"  # Optional - will auto-discover if not set
export HUE_API_KEY="your-hue-api-key"  # Optional - will be created during setup
```

### Task Server

A comprehensive task management system with hierarchical task organization and context support.

**Key Features:**
- SQLite database for persistent storage
- Hierarchical task structure (tasks can have subtasks)
- Context-based organization (separate workspaces)
- Markdown support for detailed how-to guides
- Deadlines and completion tracking

**Tools:**
- `context_create()` - Create new context/workspace
- `context_delete()` - Delete a context
- `context_list()` - List all contexts
- `task_create()` - Create new task with optional parent
- `task_update()` - Update task properties
- `task_delete()` - Delete task and subtasks
- `task_get()` - Get task with full subtask hierarchy
- `task_list()` - List all top-level tasks in context
- `task_toggle_completion()` - Toggle task completion status
- `task_move()` - Move tasks between parents/contexts

### Template Server

A minimal starting point for creating new MCP servers.

**Features:**
- Basic FastMCP server setup
- Example tool and resource registration
- Standard project structure
- Docker support included

**Example Tools:**
- `echo()` - Simple echo tool demonstrating parameter handling

## Claude Desktop Configuration

To use these servers with Claude Desktop, add entries to your `claude_desktop_config.json`:

### Using Local Python

```json
{
  "mcpServers": {
    "phillips_hue": {
      "command": "mcp",
      "args": ["run", "main.py"],
      "cwd": "/path/to/mcp-servers/phillips_hue_server"
    },
    "task_server": {
      "command": "mcp",
      "args": ["run", "main.py"],
      "cwd": "/path/to/mcp-servers/todo_server"
    }
  }
}
```

### Using Docker

```json
{
  "mcpServers": {
    "phillips_hue": {
      "command": "docker",
      "args": [
        "run", "-i", "--rm",
        "--mount", "type=bind,src=/path/to/phillips_hue_server,dst=/app",
        "phillips-hue-server"
      ]
    },
    "task_server": {
      "command": "docker",
      "args": [
        "run", "-i", "--rm",
        "--mount", "type=bind,src=/path/to/todo_server,dst=/app",
        "task-server"
      ]
    }
  }
}
```

## Development

### Project Structure

All servers follow a consistent structure:

```
server_name/
├── main.py              # Entry point
├── server.py            # Tool and resource registration
├── utils/               # Business logic modules
├── requirements.txt     # Dependencies
├── pyproject.toml       # Project metadata
├── Dockerfile          # Docker configuration
└── README.md           # Server documentation
```

### Creating a New Server

1. Copy the `template/` directory
2. Update `server.py` with your tools
3. Add business logic to `utils/`
4. Update dependencies in `pyproject.toml` and `requirements.txt`
5. Update the README with usage instructions

### Best Practices

- Use the `@mcp.tool()` decorator for synchronous tools
- Use `@mcp.async_tool()` for tools that yield progress updates
- Include comprehensive docstrings for all tools
- Handle errors gracefully with try/except blocks
- Return structured dictionaries with success/error fields
- Use type hints for all parameters and return values

## Requirements

- Python 3.12 or higher
- `mcp[cli]` package
- Additional dependencies per server (see individual `requirements.txt`)

## License

MIT License - See individual server directories for specific licensing information.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Add your server or improvements
4. Ensure all tools have proper documentation
5. Submit a pull request

## Support

For issues or questions:
- Check individual server READMEs for specific setup instructions
- Review the example implementations in `template/`
- Submit issues on the GitHub repository