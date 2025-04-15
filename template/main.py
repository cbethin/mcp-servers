# Entry point for the MCP server template
from server import mcp

if __name__ == "__main__":
    print("Starting MCP Template Server...")
    try:
        mcp.run()
    except Exception as e:
        print(f"Error starting MCP Template Server: {e}")
