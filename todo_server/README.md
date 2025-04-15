# Task MCP Server

This is an MCP server implementation for managing tasks and contexts, using SQLite and SQLAlchemy for persistent storage. Each task represents a high-level item, which may have subtasks or a how-to guide attached.

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
   docker build -t task_server .
   ```
2. Run the server in a Docker container:
   ```sh
   docker run -i --rm task_server
   ```
3. (Optional) To mount your local code for live development and persist the SQLite database:
   ```sh
   docker run -i --rm --mount type=bind,src=$(pwd),dst=/app task_server
   ```

## Claude Desktop Server Configuration Example

To use this server with Claude Desktop, add an entry to your `claude_desktop_config.json` under the `mcpServers` section. Here are two example configurations:

### Using Docker
```json
"task_server": {
  "command": "docker",
  "args": [
    "run",
    "-i",
    "--rm",
    "--mount",
    "type=bind,src=/Users/charlesbethin/Developer/Local/mcp-servers/task-management-server,dst=/app",
    "task_server"
  ]
}
```
Replace `task_server` with the name you used when building your Docker image.

### Using mcp install (local Python)
```json
"task_server": {
  "command": "mcp",
  "args": [
    "run",
    "main.py"
  ],
  "cwd": "/Users/charlesbethin/Developer/Local/mcp-servers/task-management-server"
}
```

Add either (or both) of these entries to your `claude_desktop_config.json` depending on your preferred setup.

## Structure
- `main.py`: Entry point for the server
- `server.py`: Register your tools/resources here
- `utils/`: Business logic and database management modules (e.g., `task_manager.py`)
- `db.sqlite3`: SQLite database file (auto-created)
- `tasks.json`: (Legacy) JSON file for tasks, now replaced by SQLite

---
Generated on 2025-04-15
