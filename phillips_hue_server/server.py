# Philips Hue MCP server setup
import logging
import os
import requests
from typing import Dict, List, Optional, Any, Union
from mcp.server.fastmcp import FastMCP

from utils import hue_api

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(name)s %(message)s')
logger = logging.getLogger("phillips_hue_server")

# Create the MCP server instance
phillips_hue_server_name = "phillips_hue_server"
mcp = FastMCP(
    phillips_hue_server_name, 
    instructions="""
     Always test the connection to the Philips Hue Bridge before using any other tools.
     Try connecting twice before giving up.
     
     The tools directly mirror the Philips Hue REST API endpoints with very similar parameters.
     You can refer to lights and groups by either ID or name.
    """)

# Philips Hue Tools

@mcp.tool()
def test_connection() -> Dict[str, Any]:
    """
    Test the connection to the Philips Hue Bridge.
    Returns connection status and basic bridge information if successful.
    """
    logger.info("Testing connection to Philips Hue Bridge")
    return hue_api.test_connection()

@mcp.tool()
def get_lights() -> Dict[str, Any]:
    """
    Get a list of all Philips Hue lights and their current states.
    Corresponds to GET /api/<username>/lights in the Hue API.
    """
    logger.info("Getting all Philips Hue lights")
    return hue_api.get_all_lights()

@mcp.tool()
def get_light(light_id: Union[str, int]) -> Dict[str, Any]:
    """
    Get detailed information about a specific Philips Hue light.
    Corresponds to GET /api/<username>/lights/<id> in the Hue API.
    
    Parameters:
    - light_id: The ID or name of the light to get information about
    """
    logger.info(f"Getting information for light {light_id}")
    return hue_api.get_light_info(light_id)

@mcp.tool()
def set_light_state(light_id: Union[str, int], state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Set the state of a Philips Hue light.
    Corresponds to PUT /api/<username>/lights/<id>/state in the Hue API.
    
    Parameters:
    - light_id: The ID or name of the light to control
    - state: Dictionary containing state parameters, such as:
        - on: bool - Turn light on/off
        - bri: int - Brightness (1-254)
        - hue: int - Hue (0-65535)
        - sat: int - Saturation (0-254)
        - xy: list - [x, y] coordinates in CIE color space
        - ct: int - Mired color temperature (153-500)
        - alert: str - "none", "select", "lselect"
        - effect: str - "none", "colorloop"
        - transitiontime: int - Transition time in 100ms units
    
    Example:
    ```
    set_light_state("Kitchen Light", {"on": True, "bri": 254, "hue": 10000, "sat": 254})
    ```
    """
    logger.info(f"Setting state for light {light_id}: {state}")
    return hue_api.set_light_state(light_id, state)

@mcp.tool()
def get_groups() -> Dict[str, Any]:
    """
    Get a list of all Philips Hue light groups.
    Corresponds to GET /api/<username>/groups in the Hue API.
    """
    logger.info("Getting all Philips Hue light groups")
    return hue_api.get_all_groups()

@mcp.tool()
def set_group_state(group_id: Union[str, int], state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Set the state of a Philips Hue light group.
    Corresponds to PUT /api/<username>/groups/<id>/action in the Hue API.
    
    Parameters:
    - group_id: The ID or name of the group to control
    - state: Dictionary containing state parameters, same as set_light_state
    
    Example:
    ```
    set_group_state("Living Room", {"on": True, "bri": 254})
    ```
    """
    logger.info(f"Setting state for group {group_id}: {state}")
    return hue_api.set_group_state(group_id, state)

@mcp.tool()
def get_scenes() -> Dict[str, Any]:
    """
    Get a list of all available Philips Hue scenes.
    Corresponds to GET /api/<username>/scenes in the Hue API.
    """
    logger.info("Getting all Philips Hue scenes")
    return hue_api.get_all_scenes()

@mcp.tool()
def activate_scene(group_id: Union[str, int], scene: str) -> Dict[str, Any]:
    """
    Activate a specific Philips Hue scene for a group.
    
    Parameters:
    - group_id: The ID or name of the group to apply the scene to
    - scene: The ID or name of the scene to activate
    
    Example:
    ```
    activate_scene("Living Room", "Relax")
    ```
    """
    logger.info(f"Activating scene {scene} for group {group_id}")
    return hue_api.activate_scene(group_id, scene)

@mcp.tool()
def get_group(group_id: Union[str, int]) -> Dict[str, Any]:
    """
    Get detailed information about a specific Philips Hue group.
    Corresponds to GET /api/<username>/groups/<id> in the Hue API.
    
    Parameters:
    - group_id: The ID or name of the group to get information about
    """
    logger.info(f"Getting information for group {group_id}")
    
    # Resolve the group ID
    resolved_id = hue_api.parse_identifier(group_id, "groups")
    
    base_url = hue_api.get_base_url()
    if not base_url:
        return {"success": False, "error": "Missing Hue Bridge configuration"}
    
    try:
        response = requests.get(f"{base_url}/groups/{resolved_id}")
        response.raise_for_status()
        return {"success": True, "group": response.json()}
    except requests.exceptions.RequestException as e:
        logger.error(f"Error getting group info for group {group_id}: {e}")
        return {"success": False, "error": str(e)}

@mcp.tool()
def get_scene(scene_id: str) -> Dict[str, Any]:
    """
    Get detailed information about a specific Philips Hue scene.
    Corresponds to GET /api/<username>/scenes/<id> in the Hue API.
    
    Parameters:
    - scene_id: The ID or name of the scene to get information about
    """
    logger.info(f"Getting information for scene {scene_id}")
    
    # Check if scene_id is actually a scene name
    if not any(c in scene_id for c in ['-', '/']):  # Hue scene IDs contain these characters
        scene_by_name = hue_api.get_scene_by_name(scene_id)
        if scene_by_name:
            scene_id = scene_by_name
    
    base_url = hue_api.get_base_url()
    if not base_url:
        return {"success": False, "error": "Missing Hue Bridge configuration"}
    
    try:
        response = requests.get(f"{base_url}/scenes/{scene_id}")
        response.raise_for_status()
        return {"success": True, "scene": response.json()}
    except requests.exceptions.RequestException as e:
        logger.error(f"Error getting scene info for scene {scene_id}: {e}")
        return {"success": False, "error": str(e)}

@mcp.tool()
def get_bridge_config() -> Dict[str, Any]:
    """
    Get the bridge configuration from the Philips Hue Bridge.
    Corresponds to GET /api/<username>/config in the Hue API.
    """
    logger.info("Getting bridge configuration")
    
    base_url = hue_api.get_base_url()
    if not base_url:
        return {"success": False, "error": "Missing Hue Bridge configuration"}
    
    try:
        response = requests.get(f"{base_url}/config")
        response.raise_for_status()
        return {"success": True, "config": response.json()}
    except requests.exceptions.RequestException as e:
        logger.error(f"Error getting bridge configuration: {e}")
        return {"success": False, "error": str(e)}

@mcp.tool()
def create_group(name: str, lights: List[Union[str, int]]) -> Dict[str, Any]:
    """
    Create a new group of lights.
    Corresponds to POST /api/<username>/groups in the Hue API.
    
    Parameters:
    - name: Name for the new group
    - lights: List of light IDs or names to include in the group
    
    Example:
    ```
    create_group("My Group", ["1", "2", "Kitchen Light"])
    ```
    """
    logger.info(f"Creating group '{name}' with lights: {lights}")
    
    base_url = hue_api.get_base_url()
    if not base_url:
        return {"success": False, "error": "Missing Hue Bridge configuration"}
    
    # Resolve any light names to IDs
    resolved_lights = []
    for light in lights:
        resolved_lights.append(str(hue_api.parse_identifier(light, "lights")))
    
    try:
        response = requests.post(
            f"{base_url}/groups",
            json={"name": name, "lights": resolved_lights}
        )
        response.raise_for_status()
        return {"success": True, "result": response.json()}
    except requests.exceptions.RequestException as e:
        logger.error(f"Error creating group: {e}")
        return {"success": False, "error": str(e)}

@mcp.tool()
def delete_group(group_id: Union[str, int]) -> Dict[str, Any]:
    """
    Delete a group.
    Corresponds to DELETE /api/<username>/groups/<id> in the Hue API.
    
    Parameters:
    - group_id: The ID or name of the group to delete
    
    Note: You cannot delete default groups (e.g., "Bedroom", "Living room").
    """
    logger.info(f"Deleting group {group_id}")
    
    # Resolve the group ID
    resolved_id = hue_api.parse_identifier(group_id, "groups")
    
    base_url = hue_api.get_base_url()
    if not base_url:
        return {"success": False, "error": "Missing Hue Bridge configuration"}
    
    try:
        response = requests.delete(f"{base_url}/groups/{resolved_id}")
        response.raise_for_status()
        return {"success": True, "result": response.json()}
    except requests.exceptions.RequestException as e:
        logger.error(f"Error deleting group {group_id}: {e}")
        return {"success": False, "error": str(e)}

@mcp.tool()
def turn_all_lights_off() -> Dict[str, Any]:
    """
    Turn off all lights connected to the Hue Bridge.
    This uses the special group 0, which contains all lights.
    """
    logger.info("Turning off all lights")
    return hue_api.turn_all_lights_off()

# Philips Hue Resources

@mcp.resource("phillips-hue-server://status")
def bridge_status() -> Dict[str, Any]:
    """
    Get the current status of the Philips Hue Bridge connection.
    """
    logger.info("Getting Philips Hue Bridge status")
    status = hue_api.test_connection()
    if not status["success"]:
        return {
            "connected": False,
            "error": status.get("error", "Unknown error")
        }
    
    return {
        "connected": True,
        "bridge_info": status.get("data", {})
    }

@mcp.resource("phillips-hue-server://config")
def bridge_config() -> Dict[str, Any]:
    """
    Get the configuration information for the Philips Hue Bridge.
    """
    logger.info("Getting Philips Hue Bridge configuration")
    return {
        "bridge_ip": os.environ.get('HUE_BRIDGE_IP', 'Not configured'),
        "api_key_configured": bool(os.environ.get('HUE_API_KEY'))
    }