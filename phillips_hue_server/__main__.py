#!/usr/bin/env python3
"""Entry point for the Phillips Hue MCP server when run as a module."""
from server import mcp

if __name__ == "__main__":
    mcp.run()