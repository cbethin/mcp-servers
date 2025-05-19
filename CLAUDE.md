# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository Overview

This repository contains a collection of MCP (Model Context Protocol) servers that enable Claude to interact with external systems through tool calls. Each server follows a similar structure but provides different functionality.

## Server Types

1. **Task Server** (`todo_server/`): Manages tasks with SQLite/SQLAlchemy storage
2. **Phillips Hue Server** (`phillips_hue_server/`): Controls Philips Hue smart lighting
3. **Template Server** (`template/`): Base template for creating new MCP servers

## Common Commands

### Setup and Installation

```sh
# Install uv package manager (if not already installed)
pip install uv

# Create and activate virtual environment
uv venv
source .venv/bin/activate

# Install dependencies
uv sync

# Run in development mode
mcp dev main.py

# Install to Claude MCP configuration
mcp install main.py
```

### Docker Operations

```sh
# Build Docker image
docker build -t [server-name] .

# Run in Docker container
docker run -i --rm [server-name]

# Run with local code mounted for development
docker run -i --rm --mount type=bind,src=$(pwd),dst=/app [server-name]
```

## Server Architecture

All servers follow a common structure:

- `main.py`: Entry point that creates and runs the MCP server
- `server.py`: Registers tools and resources with the MCP server
- `utils/`: Contains specialized modules with business logic
- `requirements.txt` & `pyproject.toml`: Define dependencies

## Server-Specific Configuration

### Phillips Hue Server

Requires environment variables for Bridge IP and API key:

```sh
export HUE_BRIDGE_IP="192.168.1.X"
export HUE_API_KEY="your-hue-api-key"
```

### Task Server

Uses SQLite database for persistent storage (auto-created on first run).

## Development Guidelines

1. **Implementing MCP Tools**:
   - Tools are defined as Python functions with `@mcp.tool()` decorator
   - Resources are defined with `@mcp.resource()` decorator
   - Each tool should have clear parameter and return type definitions
   - Include comprehensive docstrings for all tools

2. **Error Handling**:
   - Use try/except blocks with informative error messages
   - Return structured error responses that Claude can understand

3. **Dependencies**: 
   - All servers require Python 3.12+ and the `mcp[cli]` package
   - Add specialized dependencies to both `pyproject.toml` and `requirements.txt`