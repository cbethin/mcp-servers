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
5. (Optional) Install the MCP server to your Claude MCP configuration:
   ```sh
   mcp install main.py
   ```

## Structure
- `main.py`: Entry point for the server
- `server.py`: Register your tools/resources here
- `utils/`: Add your business logic modules here

---
Generated on 2025-04-15
