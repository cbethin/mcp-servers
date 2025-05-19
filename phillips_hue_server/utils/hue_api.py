"""
Philips Hue API utility functions for interacting with Hue Bridge and lights.
"""
import os
import requests
import logging
from typing import Dict, List, Optional, Any, Union

logger = logging.getLogger("hue_api")

# Get Hue Bridge configuration from environment variables
HUE_BRIDGE_IP = os.environ.get('HUE_BRIDGE_IP')
HUE_API_KEY = os.environ.get('HUE_API_KEY')

# Base URL for the Hue API
def get_base_url() -> str:
    """Get the base URL for the Hue API."""
    if not HUE_BRIDGE_IP:
        logger.warning("HUE_BRIDGE_IP environment variable not set.")
        return ""
    if not HUE_API_KEY:
        logger.warning("HUE_API_KEY environment variable not set.")
        return ""
    return f"http://{HUE_BRIDGE_IP}/api/{HUE_API_KEY}"

def test_connection() -> Dict[str, Any]:
    """Test the connection to the Hue Bridge."""
    base_url = get_base_url()
    if not base_url:
        return {"success": False, "error": "Missing Hue Bridge configuration"}
    
    try:
        response = requests.get(base_url)
        response.raise_for_status()
        return {"success": True, "data": response.json()}
    except requests.exceptions.RequestException as e:
        logger.error(f"Error connecting to Hue Bridge: {e}")
        return {"success": False, "error": str(e)}

def get_all_lights() -> Dict[str, Any]:
    """Get all lights connected to the Hue Bridge."""
    base_url = get_base_url()
    if not base_url:
        return {"success": False, "error": "Missing Hue Bridge configuration"}
    
    try:
        response = requests.get(f"{base_url}/lights")
        response.raise_for_status()
        return {"success": True, "lights": response.json()}
    except requests.exceptions.RequestException as e:
        logger.error(f"Error getting lights: {e}")
        return {"success": False, "error": str(e)}

def get_light_info(light_id: Union[str, int]) -> Dict[str, Any]:
    """Get information about a specific light."""
    base_url = get_base_url()
    if not base_url:
        return {"success": False, "error": "Missing Hue Bridge configuration"}
    
    # Try to resolve light name to ID if needed
    resolved_id = parse_identifier(light_id, "lights")
    
    try:
        response = requests.get(f"{base_url}/lights/{resolved_id}")
        response.raise_for_status()
        return {"success": True, "light": response.json()}
    except requests.exceptions.RequestException as e:
        logger.error(f"Error getting light info for light {light_id}: {e}")
        return {"success": False, "error": str(e)}

def parse_identifier(identifier: Union[str, int], object_type: str) -> Union[str, int]:
    """
    Try to resolve a name to an ID for lights or groups.
    
    Parameters:
    - identifier: Name or ID of the object
    - object_type: Either "lights" or "groups"
    
    Returns the ID if found, otherwise returns the original identifier.
    """
    # If it's already an ID (int or string that can be converted to int), return as is
    if isinstance(identifier, int) or (isinstance(identifier, str) and identifier.isdigit()):
        return identifier
    
    # If it's a name, try to find the corresponding ID
    base_url = get_base_url()
    if not base_url:
        return identifier
    
    try:
        # Get all objects of the specified type
        response = requests.get(f"{base_url}/{object_type}")
        response.raise_for_status()
        objects = response.json()
        
        # Look for an object with a matching name
        for id, obj in objects.items():
            if obj.get("name", "").lower() == identifier.lower():
                return id
        
        # If not found, log a warning and return the original
        logger.warning(f"Could not find {object_type[:-1]} with name '{identifier}'")
        return identifier
    
    except requests.exceptions.RequestException as e:
        logger.error(f"Error retrieving {object_type}: {e}")
        return identifier

def set_light_state(light_id: Union[str, int], state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Set the state of a light.
    
    Parameters:
    - light_id: ID or name of the light to control
    - state: Dictionary containing state parameters, such as:
        - on: bool - Turn light on/off
        - bri: int - Brightness (1-254)
        - hue: int - Hue (0-65535)
        - sat: int - Saturation (0-254)
        - xy: [float, float] - CIE xy color coordinates
        - ct: int - Color temperature (153-500)
        - alert: str - "none", "select", "lselect"
        - effect: str - "none", "colorloop"
        - transitiontime: int - Transition time in 100ms units
    """
    base_url = get_base_url()
    if not base_url:
        return {"success": False, "error": "Missing Hue Bridge configuration"}
    
    # Try to resolve light name to ID if needed
    resolved_id = parse_identifier(light_id, "lights")
    
    try:
        response = requests.put(f"{base_url}/lights/{resolved_id}/state", json=state)
        response.raise_for_status()
        return {"success": True, "result": response.json()}
    except requests.exceptions.RequestException as e:
        logger.error(f"Error setting state for light {light_id}: {e}")
        return {"success": False, "error": str(e)}

def get_all_groups() -> Dict[str, Any]:
    """Get all light groups from the Hue Bridge."""
    base_url = get_base_url()
    if not base_url:
        return {"success": False, "error": "Missing Hue Bridge configuration"}
    
    try:
        response = requests.get(f"{base_url}/groups")
        response.raise_for_status()
        return {"success": True, "groups": response.json()}
    except requests.exceptions.RequestException as e:
        logger.error(f"Error getting groups: {e}")
        return {"success": False, "error": str(e)}

def set_group_state(group_id: Union[str, int], state: Dict[str, Any]) -> Dict[str, Any]:
    """Set the state of a light group."""
    base_url = get_base_url()
    if not base_url:
        return {"success": False, "error": "Missing Hue Bridge configuration"}
    
    # Try to resolve group name to ID if needed
    resolved_id = parse_identifier(group_id, "groups")
    
    try:
        response = requests.put(f"{base_url}/groups/{resolved_id}/action", json=state)
        response.raise_for_status()
        return {"success": True, "result": response.json()}
    except requests.exceptions.RequestException as e:
        logger.error(f"Error setting state for group {group_id}: {e}")
        return {"success": False, "error": str(e)}

def get_all_scenes() -> Dict[str, Any]:
    """Get all scenes from the Hue Bridge."""
    base_url = get_base_url()
    if not base_url:
        return {"success": False, "error": "Missing Hue Bridge configuration"}
    
    try:
        response = requests.get(f"{base_url}/scenes")
        response.raise_for_status()
        return {"success": True, "scenes": response.json()}
    except requests.exceptions.RequestException as e:
        logger.error(f"Error getting scenes: {e}")
        return {"success": False, "error": str(e)}

def get_scene_by_name(scene_name: str) -> Optional[str]:
    """Find a scene ID by its name."""
    base_url = get_base_url()
    if not base_url:
        return None
    
    try:
        response = requests.get(f"{base_url}/scenes")
        response.raise_for_status()
        scenes = response.json()
        
        # Look for a scene with a matching name
        for scene_id, scene in scenes.items():
            if scene.get("name", "").lower() == scene_name.lower():
                return scene_id
        
        return None
    except requests.exceptions.RequestException as e:
        logger.error(f"Error retrieving scenes: {e}")
        return None

def activate_scene(group_id: Union[str, int], scene_id: str) -> Dict[str, Any]:
    """Activate a scene for a specific group."""
    base_url = get_base_url()
    if not base_url:
        return {"success": False, "error": "Missing Hue Bridge configuration"}
    
    # Try to resolve group name to ID
    resolved_group_id = parse_identifier(group_id, "groups")
    
    # Check if scene_id is actually a scene name
    if not any(c in scene_id for c in ['-', '/']):  # Hue scene IDs contain these characters
        scene_by_name = get_scene_by_name(scene_id)
        if scene_by_name:
            scene_id = scene_by_name
    
    try:
        response = requests.put(
            f"{base_url}/groups/{resolved_group_id}/action", 
            json={"scene": scene_id}
        )
        response.raise_for_status()
        return {"success": True, "result": response.json()}
    except requests.exceptions.RequestException as e:
        logger.error(f"Error activating scene {scene_id} for group {group_id}: {e}")
        return {"success": False, "error": str(e)}

def turn_all_lights_off() -> Dict[str, Any]:
    """Turn off all lights connected to the bridge."""
    # Group 0 is all lights
    return set_group_state(0, {"on": False})