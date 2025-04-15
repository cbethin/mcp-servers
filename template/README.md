# MCP Server Template

This is a minimal template for creating a new MCP server using FastMCP.

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

To use this server with Claude Desktop, add an entry to your `claude_desktop_config.json` under the `mcpServers` section. Here are two example configurations:

### Using Docker
```json
"template_server": {
  "command": "docker",
  "args": [
    "run",
    "-i",
    "--rm",
    "--mount",
    "type=bind,src=/Users/charlesbethin/Developer/Local/mcp-servers/template,dst=/app",
    "my-mcp-server"
  ]
}
```
Replace `my-mcp-server` with the name you used when building your Docker image.

### Using mcp install (local Python)
```json
"template_server": {
  "command": "mcp",
  "args": [
    "run",
    "main.py"
  ],
  "cwd": "/Users/charlesbethin/Developer/Local/mcp-servers/template"
}
```

Add either (or both) of these entries to your `claude_desktop_config.json` depending on your preferred setup.

## Structure
- `main.py`: Entry point for the server
- `server.py`: Register your tools/resources here
- `utils/`: Add your business logic modules here

---
Generated on 2025-04-15
