# Entry point for the Phillips Hue MCP server
from server import mcp

if __name__ == "__main__":
    print("Starting Phillips Hue MCP Server...")
    try:
        mcp.run()
    except Exception as e:
        print(f"Error starting Phillips Hue MCP Server: {e}")
