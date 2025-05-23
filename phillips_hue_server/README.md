# Phillips Hue MCP Server

This is an MCP (Model Context Protocol) server for controlling Phillips Hue smart lighting through Claude. It allows Claude to interact with your Phillips Hue lights via tool calls.

## Overview

This server implements the Model Context Protocol (MCP) to allow Claude to control Phillips Hue lights. With this server, Claude can:

- Get information about your Hue lights and their current state
- Turn lights on and off
- Change light brightness, color, and scenes
- Group lights and create custom behaviors

## Installation

### Prerequisites
- Python 3.10 or higher
- [`uv`](https://github.com/astral-sh/uv) package manager

### Quick Start

1. Clone or download this repository
2. Navigate to the server directory:
   ```sh
   cd /path/to/phillips_hue_server
   ```
3. Install dependencies using uv:
   ```sh
   uv add "mcp>=1.0.0" requests urllib3
   ```
4. Test the server locally:
   ```sh
   uv run mcp dev server.py
   ```

### Installing as a Package

For a more robust installation, you can install the server as a package:

```sh
# From the phillips_hue_server directory
uv pip install -e .
```

This installs the server and all its dependencies in development mode.

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

## Claude Desktop Server Configuration

To use this server with Claude Desktop, you need to edit your `claude_desktop_config.json` file.

### Finding your config file:
- macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`
- Windows: `%APPDATA%\Claude\claude_desktop_config.json`
- Linux: `~/.config/Claude/claude_desktop_config.json`

### Configuration Options:

#### Option 1: Using uv (Recommended)
This ensures all dependencies are properly loaded:

```json
{
  "mcpServers": {
    "phillips_hue_server": {
      "command": "uv",
      "args": ["run", "mcp", "run", "server.py"],
      "cwd": "/path/to/phillips_hue_server"
    }
  }
}
```

#### Option 2: Using Python module
If you installed the server as a package:

```json
{
  "mcpServers": {
    "phillips_hue_server": {
      "command": "python",
      "args": ["-m", "mcp", "run", "/path/to/phillips_hue_server/server.py"]
    }
  }
}
```

#### Option 3: Direct execution with virtual environment
If other methods fail:

```json
{
  "mcpServers": {
    "phillips_hue_server": {
      "command": "/path/to/phillips_hue_server/.venv/bin/python",
      "args": ["-m", "mcp", "run", "server.py"],
      "cwd": "/path/to/phillips_hue_server"
    }
  }
}
```

**Important Notes:**
- Replace `/path/to/phillips_hue_server` with your actual path
- Restart Claude Desktop after editing the config
- Check Claude Desktop logs if the server doesn't appear

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

### Bridge Discovery Issues

If automatic bridge discovery is timing out:

1. **Enable debug logging** to see detailed discovery attempts:
   ```sh
   DEBUG=1 mcp dev main.py
   ```

2. **Try manual discovery** if you know your bridge IP:
   ```
   # In Claude, use:
   check_bridge_at_ip("192.168.1.100")  # Replace with your bridge IP
   ```

3. **Common bridge IP ranges**:
   - `192.168.1.x` (most common)
   - `10.0.0.x`
   - `192.168.0.x`
   - Check your router's DHCP client list for "Philips Hue"

4. **Discovery methods used** (in order):
   - Cloud discovery via discovery.meethue.com
   - mDNS/hostname resolution (philips-hue.local)
   - Network scan of common IPs

### Connection Issues

- The bridge now uses HTTPS (port 443) for API v2, though HTTP (port 80) is still supported
- Self-signed certificates are handled automatically
- Ensure your bridge has internet access for cloud discovery

### Debug Information

When debug mode is enabled (`DEBUG=1`), the server logs:
- Each discovery method attempted
- IP addresses being checked
- API response details
- Bridge validation steps

### Other Issues

- If you can't connect to your Hue Bridge, verify the IP address is correct and that you're on the same network
- Ensure your API key/username is valid and has the necessary permissions
- Check the server logs for detailed error messages

## Resources

- [Philips Hue API Documentation](https://developers.meethue.com/develop/hue-api/)
- [Model Context Protocol Documentation](https://docs.anthropic.com/claude/docs/model-context-protocol-mcp)

---
Generated on 2025-05-15
