# Template MCP server setup
import logging
from mcp.server.fastmcp import FastMCP

from utils.example_utils import example_utility_function

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(name)s %(message)s')
logger = logging.getLogger("template_server")

# Create the MCP server instance
template_server_name = "template_server"
mcp = FastMCP(template_server_name)

# Example tool registration
@mcp.tool()
def echo(param: str) -> dict:
    """
    Example Echo tool for the MCP server template.
    Replace or extend this with your own tools.
    """
    logger.info(f"example_tool called with param: {param}")
    result = example_utility_function(param)
    return {"message": f"You sent: {result}"}

# Example resource registration
@mcp.resource("template-server://example")
def example_resource() -> dict:
    """
    Example resource for the MCP server template.
    Replace or extend this with your own resources.
    """
    return {"resource": "example"}
