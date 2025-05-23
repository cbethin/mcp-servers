#!/usr/bin/env python3
"""Entry point for the Phillips Hue MCP server"""
import sys
import os

# Add the current directory to Python path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from server import mcp
except ImportError as e:
    print(f"Import error: {e}", file=sys.stderr)
    print(f"Python path: {sys.path}", file=sys.stderr)
    print(f"Current directory: {os.getcwd()}", file=sys.stderr)
    raise

if __name__ == "__main__":
    print("Starting Phillips Hue MCP Server...", file=sys.stderr)
    try:
        mcp.run()
    except Exception as e:
        print(f"Error starting Phillips Hue MCP Server: {e}", file=sys.stderr)
        raise
