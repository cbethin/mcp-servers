#!/usr/bin/env python3
"""
Sandbox Terminal MCP Server - Entry Point

This server provides secure sandboxed terminal command execution
within isolated Docker containers.
"""

import logging
import sys
from pathlib import Path

# Add the current directory to Python path for imports
sys.path.insert(0, str(Path(__file__).parent))

from server import mcp

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

if __name__ == "__main__":
    # Run the MCP server
    mcp.run()