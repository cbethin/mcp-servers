# Phillips Hue MCP Server

This is an MCP (Model Context Protocol) server for controlling Phillips Hue smart lighting through Claude. It allows Claude to interact with your Phillips Hue lights via tool calls.

## Overview

This server implements the Model Context Protocol (MCP) to allow Claude to control Phillips Hue lights. With this server, Claude can:

- Get information about your Hue lights and their current state
- Turn lights on and off
- Change light brightness, color, and scenes
- Group lights and create custom behaviors

## Getting Started

1. Make sure [`uv`](https://github.com/astral-sh/uv) is installed:
   ```sh
   pip install uv
   ```
2. Create a virtual environment and activate it:
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
5. Install the MCP server to your Claude MCP configuration (local install):
   ```sh
   mcp install main.py
   ```

## Running with Docker

1. Build the Docker image:
   ```sh
   docker build -t my-mcp-server .
   ```
2. Run the server in a Docker container:
   ```sh
   docker run -i --rm my-mcp-server
   ```
3. (Optional) To mount your local code for live development:
   ```sh
   docker run -i --rm --mount type=bind,src=$(pwd),dst=/app my-mcp-server
   ```

## Claude Desktop Server Configuration Example

To use this server with Claude Desktop, add an entry to your `claude_desktop_config.json` under the `mcpServers` section:

```json
"phillips_hue_server": {
  "command": "mcp",
  "args": [
    "run",
    "main.py"
  ],
  "cwd": "/Users/charlesbethin/Developer/Local/mcp-servers/phillips_hue_server"
}
```

## Prerequisites

- Phillips Hue Bridge configured on your network
- Phillips Hue lights set up and working with the Hue app
- API credentials for your Hue Bridge (see Configuration section)

## Setting up Phillips Hue API Access

1. Find your Hue Bridge IP address (check your router or the Hue app)
2. Generate an API key/username by following the [official Philips Hue API documentation](https://developers.meethue.com/develop/get-started-2/)
3. Add your Bridge IP and API key to your environment variables or directly in the code (see Configuration section)

## Configuration

Set your Phillips Hue Bridge IP and API key in one of these ways:

1. Environment variables:
   ```sh
   export HUE_BRIDGE_IP="192.168.1.X"
   export HUE_API_KEY="your-hue-api-key"
   ```

2. Or update these values directly in the server code (not recommended for security reasons)

## Structure
- `main.py`: Entry point for the server
- `server.py`: Register your tools/resources here
- `utils/`: Add your business logic modules here

## Available Tools

The Phillips Hue MCP server exposes the following tools to Claude:

### Current Example Tool

- `echo`: A simple echo tool that demonstrates the structure of MCP tools (to be replaced with actual Hue tools)

### Planned Hue Tools (to be implemented)

- `get_lights`: Retrieve a list of all available Hue lights and their current states
- `set_light_state`: Turn lights on/off or change their brightness/color
- `get_groups`: Get information about light groups
- `set_group_state`: Control light groups
- `get_scenes`: List available lighting scenes
- `activate_scene`: Enable a specific lighting scene

## How to Add New Tools

1. Add new functions to interact with the Hue API in the `utils/` directory
2. Register new tools in `server.py` using the `@mcp.tool()` decorator
3. Define clear parameters and return types for each tool

Example of adding a new tool in `server.py`:

```python
@mcp.tool()
def get_lights() -> dict:
    """
    Get a list of all Phillips Hue lights and their current states.
    """
    lights = hue_api.get_all_lights()  # Implement this function in utils
    return {"lights": lights}
```

## Troubleshooting

- If you can't connect to your Hue Bridge, verify the IP address is correct and that you're on the same network
- Ensure your API key/username is valid and has the necessary permissions
- Check the server logs for detailed error messages

## Resources

- [Philips Hue API Documentation](https://developers.meethue.com/develop/hue-api/)
- [Model Context Protocol Documentation](https://docs.anthropic.com/claude/docs/model-context-protocol-mcp)

---
Generated on 2025-05-15
