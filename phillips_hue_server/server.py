# Philips Hue MCP server setup
import json
import logging
import os
import requests
from pathlib import Path
from typing import Dict, List, Optional, Any, Union
from mcp.server.fastmcp import FastMCP

# Import our enhanced utilities
from utils import hue_api
from utils.config import hue_config, CONFIG_DIR
from utils.discovery import BridgeDiscovery
from utils.colors import ColorConverter
from utils.validation import HueValidator

# Configure logging with more detail for debugging
logging.basicConfig(
    level=logging.DEBUG if os.environ.get('DEBUG') else logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger("phillips_hue_server")

# Log startup information
logger.info("=== Phillips Hue MCP Server Starting ===")
logger.info(f"Debug mode: {'ON' if os.environ.get('DEBUG') else 'OFF'}")

# Create the MCP server instance
phillips_hue_server_name = "phillips_hue_server"
mcp = FastMCP(
    phillips_hue_server_name, 
    instructions="""
     SETUP WORKFLOW:
     1. If no bridges are configured, run quick_setup_workflow() first
     2. For new setup, run discover_bridges() to find bridges on your network
     3. Press the button on your Hue bridge, then run setup_bridge(bridge_ip)
     4. Test connection with test_connection()
     
     USAGE:
     - Use natural language colors: set_light_color_natural("Kitchen", "warm white")
     - Control groups: set_group_color_natural("Living Room", "sunset")
     - Create custom scenes: create_lighting_scene()
     - You can refer to lights and groups by either ID or name
     
     AVAILABLE COLORS:
     - Color names: red, blue, green, purple, sunset, ocean, forest, etc.
     - Temperature presets: warm_white, cool_white, daylight, candle, etc.
     - Hex codes: #FF5500, #00AAFF, etc.
     - RGB values: rgb(255,85,0)
     
     Always test the connection before other operations if setup is uncertain.
    """)

# ============================================================================
# BRIDGE MANAGEMENT TOOLS
# ============================================================================

@mcp.tool()
def discover_bridges() -> Dict[str, Any]:
    """
    Discover Philips Hue bridges on the local network.
    Returns a list of discovered bridges with their IP addresses.
    Uses multiple methods: cloud discovery, mDNS, and network scanning.
    """
    logger.info("User requested bridge discovery")
    try:
        bridges = BridgeDiscovery.discover_bridges()
        
        if bridges:
            logger.info(f"Discovery successful: {len(bridges)} bridge(s) found")
            return {"success": True, "bridges": bridges, "count": len(bridges)}
        else:
            logger.warning("No bridges discovered")
            return {
                "success": False, 
                "bridges": [],
                "error": "No bridges found",
                "help": "Try check_bridge_at_ip() if you know your bridge IP"
            }
            
    except Exception as e:
        logger.error(f"Discovery error: {type(e).__name__}: {e}")
        return {"success": False, "error": str(e)}

@mcp.tool()
def setup_bridge(bridge_ip: str, bridge_name: str = None) -> Dict[str, Any]:
    """
    Setup a new Hue bridge by creating API credentials.
    User must press the bridge button before calling this.
    
    Parameters:
    - bridge_ip: IP address of the bridge
    - bridge_name: Optional name for the bridge
    """
    logger.info(f"User initiating bridge setup for IP: {bridge_ip}")
    
    # First verify it's actually a bridge
    logger.debug(f"Verifying {bridge_ip} is a Hue bridge...")
    bridge_info = BridgeDiscovery.get_bridge_info(bridge_ip)
    
    if not bridge_info["success"]:
        logger.error(f"IP {bridge_ip} does not appear to be a Hue bridge")
        return {
            "success": False,
            "error": f"{bridge_ip} is not a Hue bridge or is not reachable"
        }
    
    logger.info(f"Confirmed bridge at {bridge_ip}: {bridge_info['info']['name']}")
    
    # Create API key
    logger.info("Waiting for button press...")
    result = BridgeDiscovery.create_api_key(bridge_ip)
    
    if result["success"]:
        # Save to configuration
        bridge_id = hue_config.add_bridge(
            bridge_ip, 
            result["api_key"], 
            bridge_name or bridge_info['info']['name']
        )
        logger.info(f"✓ Bridge setup complete! ID: {bridge_id}")
        return {
            "success": True, 
            "bridge_id": bridge_id,
            "message": "Bridge configured successfully! You can now use other tools.",
            "bridge_info": bridge_info['info']
        }
    else:
        logger.error(f"Setup failed: {result['error']}")
        return {"success": False, "error": result["error"]}

@mcp.tool()
def quick_setup_workflow() -> Dict[str, Any]:
    """
    Perform automated setup workflow:
    1. Check for existing configuration
    2. Discover bridges if none configured
    3. Guide user through setup
    """
    logger.info("Starting quick setup workflow")
    
    # Check if we already have bridges configured
    if hue_config.config.get("bridges"):
        # Test connection to verify it's working
        connection_test = hue_api.test_connection()
        if connection_test["success"]:
            return {
                "success": True,
                "message": "Bridge already configured and working!",
                "bridges": [b["name"] for b in hue_config.config["bridges"]]
            }
        else:
            return {
                "success": False,
                "message": "Bridge configured but not reachable. Please check connection.",
                "error": connection_test.get("error")
            }
    
    # Discover bridges
    discovery_result = discover_bridges()
    if not discovery_result["success"] or not discovery_result["bridges"]:
        return {
            "success": False,
            "error": "Automatic discovery didn't find any bridges",
            "suggestions": [
                "1. Ensure your bridge is powered on and connected to your network",
                "2. Check your router's device list for the bridge IP",
                "3. If you know your bridge IP, use: check_bridge_at_ip('YOUR.IP.HERE')",
                "4. Common bridge IPs: 192.168.1.x or 10.0.0.x where x is often 2-254",
                "5. Try discover_bridges() again - network scans can be intermittent"
            ],
            "manual_setup": "If you know your bridge IP: check_bridge_at_ip('192.168.1.100')"
        }
    
    bridges = discovery_result["bridges"]
    
    return {
        "success": True,
        "message": "Found bridges! Next: press the bridge button, then run setup_bridge(bridge_ip)",
        "discovered_bridges": bridges,
        "next_step": f"setup_bridge('{bridges[0]['ip']}')"
    }

@mcp.tool()
def check_bridge_at_ip(ip_address: str) -> Dict[str, Any]:
    """
    Check if a specific IP address hosts a Hue bridge.
    Useful if automatic discovery is failing but you know your bridge IP.
    
    Parameters:
    - ip_address: The IP address to check (e.g., "192.168.1.100")
    """
    logger.info(f"Checking if {ip_address} is a Hue bridge")
    
    try:
        # First try to get basic info
        bridge_info = BridgeDiscovery.get_bridge_info(ip_address)
        
        if bridge_info["success"]:
            return {
                "success": True,
                "is_bridge": True,
                "bridge_info": bridge_info["info"],
                "next_step": f"Press the bridge button, then run: setup_bridge('{ip_address}')"
            }
        else:
            return {
                "success": False,
                "is_bridge": False,
                "error": "No Hue bridge found at this IP address"
            }
    except Exception as e:
        return {
            "success": False,
            "error": f"Could not connect to {ip_address}: {str(e)}"
        }

@mcp.tool()
def list_configured_bridges() -> Dict[str, Any]:
    """
    List all configured Hue bridges.
    """
    logger.info("Listing configured bridges")
    bridges = []
    for bridge in hue_config.config["bridges"]:
        bridges.append({
            "id": bridge["id"],
            "name": bridge["name"],
            "ip": bridge["ip"],
            "api_version": bridge.get("api_version", "v1"),
            "created_at": bridge.get("created_at", "Unknown")
        })
    return {"success": True, "bridges": bridges}

@mcp.tool()
def test_connection() -> Dict[str, Any]:
    """
    Test the connection to the Philips Hue Bridge.
    Returns connection status and basic bridge information if successful.
    """
    logger.info("Testing connection to Philips Hue Bridge")
    return hue_api.test_connection()

# ============================================================================
# BASIC LIGHT CONTROL TOOLS
# ============================================================================

@mcp.tool()
def get_lights() -> Dict[str, Any]:
    """
    Get a list of all Philips Hue lights and their current states.
    """
    logger.info("Getting all Philips Hue lights")
    return hue_api.get_all_lights()

@mcp.tool()
def get_light(light_id: Union[str, int]) -> Dict[str, Any]:
    """
    Get detailed information about a specific Philips Hue light.
    
    Parameters:
    - light_id: The ID or name of the light to get information about
    """
    logger.info(f"Getting information for light {light_id}")
    return hue_api.get_light_info(light_id)

@mcp.tool()
def set_light_state(light_id: Union[str, int], state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Set the state of a Philips Hue light with validation.
    
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
    
    # Validate and clean the state
    cleaned_state = HueValidator.clean_light_state(state)
    
    if not cleaned_state:
        return {"success": False, "error": "No valid state parameters provided"}
    
    return hue_api.set_light_state(light_id, cleaned_state)

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

# ============================================================================
# ENHANCED COLOR CONTROL TOOLS
# ============================================================================

@mcp.tool()
def set_light_color_natural(light_id: Union[str, int], color_name: str, brightness: Optional[int] = None) -> Dict[str, Any]:
    """
    Set light color using natural language color names.
    
    Parameters:
    - light_id: Light to control (ID or name)
    - color_name: Color like "warm white", "cool blue", "sunset orange", "ocean", "#FF5500"
    - brightness: Optional brightness override (1-254)
    
    Examples:
    - set_light_color_natural("Kitchen", "warm white")
    - set_light_color_natural("Bedroom", "sunset", 150)
    - set_light_color_natural("Living Room", "#FF6B35")
    """
    logger.info(f"Setting light {light_id} to color {color_name}")
    
    # Parse the color
    color_state = ColorConverter.parse_color(color_name)
    
    # Override brightness if specified
    if brightness is not None:
        color_state["bri"] = max(1, min(254, brightness))
    
    # Ensure light is on
    color_state["on"] = True
    
    return hue_api.set_light_state(light_id, color_state)

@mcp.tool()
def set_group_color_natural(group_id: Union[str, int], color_name: str, brightness: Optional[int] = None) -> Dict[str, Any]:
    """
    Set group color using natural language color names.
    
    Parameters:
    - group_id: Group to control (ID or name)
    - color_name: Color like "warm white", "cool blue", "sunset orange"
    - brightness: Optional brightness override (1-254)
    """
    logger.info(f"Setting group {group_id} to color {color_name}")
    
    # Parse the color
    color_state = ColorConverter.parse_color(color_name)
    
    # Override brightness if specified
    if brightness is not None:
        color_state["bri"] = max(1, min(254, brightness))
    
    # Ensure lights are on
    color_state["on"] = True
    
    return hue_api.set_group_state(group_id, color_state)

@mcp.tool()
def get_available_colors() -> Dict[str, Any]:
    """
    Get a list of all available color names and temperature presets.
    """
    logger.info("Getting available color options")
    return {"success": True, "colors": ColorConverter.get_available_colors()}

@mcp.tool()
def suggest_colors(input_color: str) -> Dict[str, Any]:
    """
    Get color suggestions for invalid color input.
    
    Parameters:
    - input_color: The color input that didn't work
    """
    suggestions = ColorConverter.suggest_similar_colors(input_color)
    return {
        "success": True,
        "input": input_color,
        "suggestions": suggestions
    }

# ============================================================================
# SCENE MANAGEMENT TOOLS
# ============================================================================

@mcp.tool()
def get_scenes() -> Dict[str, Any]:
    """
    Get a list of all available Philips Hue scenes.
    """
    logger.info("Getting all Philips Hue scenes")
    return hue_api.get_all_scenes()

@mcp.tool()
def get_scene(scene_id: str) -> Dict[str, Any]:
    """
    Get detailed information about a specific Philips Hue scene.
    
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
        return {"success": False, "error": "No Hue Bridge configured"}
    
    try:
        response = requests.get(f"{base_url}/scenes/{scene_id}", timeout=10)
        response.raise_for_status()
        return {"success": True, "scene": response.json()}
    except requests.exceptions.RequestException as e:
        logger.error(f"Error getting scene info for scene {scene_id}: {e}")
        return {"success": False, "error": str(e)}

@mcp.tool()
def activate_scene(group_id: Union[str, int], scene: str) -> Dict[str, Any]:
    """
    Activate a specific Philips Hue scene for a group.
    
    Parameters:
    - group_id: The ID or name of the group to apply the scene to
    - scene: The ID or name of the scene to activate
    """
    logger.info(f"Activating scene {scene} for group {group_id}")
    return hue_api.activate_scene(group_id, scene)

@mcp.tool()
def apply_custom_scene(lights_config: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    """
    Apply a custom lighting configuration to multiple lights (temporary scene).
    
    Note: This doesn't create a persistent scene on the bridge, it just sets lights to specific states.
    For persistent scenes, use the Hue app or bridge API directly.
    
    Parameters:
    - lights_config: Dict mapping light names/IDs to their color/brightness settings
    
    Example:
    ```
    apply_custom_scene({
        "Desk Lamp": {"color": "warm white", "brightness": 200},
        "Ceiling Light": {"color": "daylight", "brightness": 100},
        "Accent Light": {"color": "blue", "brightness": 50}
    })
    ```
    """
    logger.info(f"Applying custom configuration to {len(lights_config)} lights")
    
    # Convert natural language to Hue states
    scene_states = {}
    for light_name, config in lights_config.items():
        try:
            light_id = hue_api.parse_identifier(light_name, "lights")
            
            if "color" in config:
                state = ColorConverter.parse_color(config["color"])
            else:
                state = {"on": True, "bri": 254}
            
            if "brightness" in config:
                state["bri"] = max(1, min(254, config["brightness"]))
            
            state["on"] = True
            scene_states[str(light_id)] = state
            
        except Exception as e:
            logger.warning(f"Skipping light {light_name}: {e}")
    
    # Apply the configuration by setting each light individually
    results = []
    for light_id, state in scene_states.items():
        result = hue_api.set_light_state(light_id, state)
        results.append({"light": light_id, "result": result})
    
    return {
        "success": True,
        "lights_configured": len(results),
        "results": results,
        "note": "This is a temporary configuration. To save as a scene, use the Hue app."
    }

@mcp.tool()
def save_scene(scene_name: str, notes: Optional[str] = None) -> Dict[str, Any]:
    """
    Save the current lighting configuration to disk as a named scene.
    
    Parameters:
    - scene_name: Name for the saved scene
    - notes: Optional notes about the scene
    
    The scene will be saved with light names, colors (hex + xy), brightness, and apply commands.
    """
    logger.info(f"Saving scene '{scene_name}'")
    
    # No strict validation on scene names to allow dates and special formatting
    import re
    from datetime import datetime
    
    # Create scenes directory in config location
    scenes_dir = CONFIG_DIR / "scenes"
    scenes_dir.mkdir(parents=True, exist_ok=True)
    
    # Get current light states
    lights_result = hue_api.get_all_lights()
    if not lights_result["success"]:
        return {"success": False, "error": "Failed to get current light states"}
    
    # Build scene data in the requested format
    scene_data = {
        "scene_name": scene_name,
        "created": datetime.now().isoformat(),
        "lights": {},
        "apply_command": {}
    }
    
    # Helper to convert xy to hex color
    def xy_to_hex(xy, brightness):
        # Simplified conversion - this is approximate
        x, y = xy
        z = 1.0 - x - y
        Y = brightness / 254.0
        X = (Y / y) * x
        Z = (Y / y) * z
        
        # Convert to RGB
        r = X * 1.656492 - Y * 0.354851 - Z * 0.255038
        g = -X * 0.707196 + Y * 1.655397 + Z * 0.036152
        b = X * 0.051713 - Y * 0.121364 + Z * 1.011530
        
        # Apply gamma correction and convert to hex
        r = max(0, min(1, r))
        g = max(0, min(1, g))
        b = max(0, min(1, b))
        
        r = int(255 * (r ** (1/2.2)))
        g = int(255 * (g ** (1/2.2)))
        b = int(255 * (b ** (1/2.2)))
        
        return f"#{r:02X}{g:02X}{b:02X}"
    
    # Save light states in the requested format
    for light_id, light_info in lights_result["lights"].items():
        light_name = light_info["name"]
        state = light_info["state"]
        
        # Build light entry
        light_entry = {
            "on": state.get("on", False),
            "brightness": state.get("bri", 254)
        }
        
        # Determine color
        if "xy" in state:
            light_entry["xy"] = state["xy"]
            light_entry["color"] = xy_to_hex(state["xy"], state.get("bri", 254))
        elif "ct" in state:
            light_entry["ct"] = state["ct"]
            # Map CT to color name
            if state["ct"] >= 450:
                light_entry["color"] = "warm_white"
            elif state["ct"] >= 350:
                light_entry["color"] = "soft_white"
            elif state["ct"] >= 250:
                light_entry["color"] = "neutral_white"
            else:
                light_entry["color"] = "cool_white"
        
        # Add reachability note
        if not state.get("reachable", True):
            light_entry["notes"] = "(currently unreachable)"
        else:
            # Add descriptive note
            brightness_pct = int((state.get("bri", 254) / 254) * 100)
            color_desc = light_entry.get("color", "white")
            light_entry["notes"] = f"{color_desc} at {brightness_pct}% brightness"
        
        scene_data["lights"][light_name] = light_entry
        
        # Build apply command
        apply_cmd = {"brightness": light_entry["brightness"]}
        if "color" in light_entry:
            apply_cmd["color"] = light_entry["color"]
        scene_data["apply_command"][light_name] = apply_cmd
    
    # Add notes if provided
    if notes:
        scene_data["notes"] = notes
    
    # Save to file - allow spaces in filename
    filename = scene_name + ".json"
    filepath = scenes_dir / filename
    
    try:
        with open(filepath, 'w') as f:
            json.dump(scene_data, f, indent=2)
        
        return {
            "success": True,
            "message": f"Scene '{scene_name}' saved successfully",
            "filename": filename,
            "lights_saved": len(scene_data["lights"]),
            "filepath": str(filepath)
        }
    except Exception as e:
        logger.error(f"Error saving scene: {e}")
        return {"success": False, "error": str(e)}

@mcp.tool()
def load_scene(scene_name: str, transition_time: Optional[int] = None) -> Dict[str, Any]:
    """
    Load and apply a previously saved scene from disk.
    
    Parameters:
    - scene_name: Name of the scene to load (without .json extension)
    - transition_time: Optional transition time in 100ms units (e.g., 10 = 1 second)
    
    Returns information about the scene application.
    """
    logger.info(f"Loading scene '{scene_name}'")
    
    # Look for scene file
    scenes_dir = CONFIG_DIR / "scenes"
    filepath = scenes_dir / f"{scene_name}.json"
    
    # Check if file exists
    if not filepath.exists():
        return {
            "success": False,
            "error": f"Scene '{scene_name}' not found",
            "available_scenes": list_saved_scenes()["scenes"]
        }
    
    # Load scene data
    try:
        with open(filepath, 'r') as f:
            scene_data = json.load(f)
    except Exception as e:
        logger.error(f"Error reading scene file: {e}")
        return {"success": False, "error": f"Error reading scene file: {str(e)}"}
    
    # Handle both new and old scene formats
    if "apply_command" in scene_data:
        # New format with apply_command
        results = []
        lights_applied = 0
        lights_failed = 0
        
        for light_name, command in scene_data["apply_command"].items():
            try:
                # Build state from command
                state = {"on": True}
                
                if "brightness" in command:
                    state["bri"] = command["brightness"]
                
                if "color" in command:
                    color_state = ColorConverter.parse_color(command["color"])
                    state.update(color_state)
                
                # Add transition time if specified
                if transition_time is not None:
                    state["transitiontime"] = transition_time
                
                # Apply the state
                result = hue_api.set_light_state(light_name, state)
                
                if result["success"]:
                    lights_applied += 1
                    results.append({
                        "light": light_name,
                        "success": True
                    })
                else:
                    lights_failed += 1
                    results.append({
                        "light": light_name,
                        "success": False,
                        "error": result.get("error", "Unknown error")
                    })
                    
            except Exception as e:
                lights_failed += 1
                logger.error(f"Error applying state to light {light_name}: {e}")
                results.append({
                    "light": light_name,
                    "success": False,
                    "error": str(e)
                })
    else:
        # Old format - backward compatibility
        results = []
        lights_applied = 0
        lights_failed = 0
        
        for light_id, light_state in scene_data.get("lights", {}).items():
            try:
                # Prepare state to apply
                state = {k: v for k, v in light_state.items() if k != "name"}
                
                # Add transition time if specified
                if transition_time is not None:
                    state["transitiontime"] = transition_time
                
                # Apply the state
                result = hue_api.set_light_state(light_id, state)
                
                if result["success"]:
                    lights_applied += 1
                    results.append({
                        "light": light_state.get("name", f"Light {light_id}"),
                        "success": True
                    })
                else:
                    lights_failed += 1
                    results.append({
                        "light": light_state.get("name", f"Light {light_id}"),
                        "success": False,
                        "error": result.get("error", "Unknown error")
                    })
                    
            except Exception as e:
                lights_failed += 1
                logger.error(f"Error applying state to light {light_id}: {e}")
                results.append({
                    "light": light_state.get("name", f"Light {light_id}"),
                    "success": False,
                    "error": str(e)
                })
    
    return {
        "success": lights_applied > 0,
        "scene_name": scene_data.get("scene_name", scene_data.get("name", scene_name)),
        "created": scene_data.get("created", scene_data.get("created_at", "Unknown")),
        "notes": scene_data.get("notes", scene_data.get("description", "")),
        "lights_applied": lights_applied,
        "lights_failed": lights_failed,
        "results": results
    }

@mcp.tool()
def list_saved_scenes() -> Dict[str, Any]:
    """
    List all saved scenes available on disk.
    
    Returns a list of scene names with their descriptions and creation times.
    """
    logger.info("Listing saved scenes")
    
    scenes_dir = CONFIG_DIR / "scenes"
    
    # Create directory if it doesn't exist
    if not scenes_dir.exists():
        scenes_dir.mkdir(parents=True, exist_ok=True)
        return {"success": True, "scenes": [], "message": "No saved scenes found"}
    
    scenes = []
    
    try:
        for filepath in scenes_dir.glob("*.json"):
            try:
                with open(filepath, 'r') as f:
                    scene_data = json.load(f)
                    # Handle both new and old format
                    scene_name = scene_data.get("scene_name", scene_data.get("name", filepath.stem))
                    created = scene_data.get("created", scene_data.get("created_at", "Unknown"))
                    notes = scene_data.get("notes", scene_data.get("description", ""))
                    
                    scenes.append({
                        "name": scene_name,
                        "filename": filepath.name,
                        "notes": notes,
                        "created": created,
                        "light_count": len(scene_data.get("lights", {})),
                        "has_apply_command": "apply_command" in scene_data
                    })
            except Exception as e:
                logger.warning(f"Error reading scene file {filepath.name}: {e}")
                scenes.append({
                    "name": filepath.stem,
                    "filename": filepath.name,
                    "error": f"Error reading file: {str(e)}"
                })
        
        # Sort by creation date (newest first)
        scenes.sort(key=lambda x: x.get("created", ""), reverse=True)
        
        return {
            "success": True,
            "scenes": scenes,
            "count": len(scenes)
        }
        
    except Exception as e:
        logger.error(f"Error listing scenes: {e}")
        return {"success": False, "error": str(e)}

@mcp.tool()
def delete_saved_scene(scene_name: str) -> Dict[str, Any]:
    """
    Delete a saved scene from disk.
    
    Parameters:
    - scene_name: Name of the scene to delete
    """
    logger.info(f"Deleting scene '{scene_name}'")
    
    # Look for scene file
    scenes_dir = CONFIG_DIR / "scenes"
    filepath = scenes_dir / f"{scene_name}.json"
    
    # Check if file exists
    if not filepath.exists():
        return {
            "success": False,
            "error": f"Scene '{scene_name}' not found"
        }
    
    try:
        filepath.unlink()
        return {
            "success": True,
            "message": f"Scene '{scene_name}' deleted successfully"
        }
    except Exception as e:
        logger.error(f"Error deleting scene: {e}")
        return {"success": False, "error": str(e)}

# ============================================================================
# CONFIGURATION MANAGEMENT TOOLS
# ============================================================================

@mcp.tool()
def show_configuration() -> Dict[str, Any]:
    """
    Show current MCP configuration including bridges and preferences.
    """
    logger.info("Showing current configuration")
    config = hue_config.config
    
    # Mask API keys for security
    safe_config = {
        "bridges": [],
        "preferences": config.get("preferences", {}),
        "version": config.get("version", "2.0")
    }
    
    for bridge in config.get("bridges", []):
        safe_bridge = bridge.copy()
        if "api_key" in safe_bridge:
            safe_bridge["api_key"] = f"{safe_bridge['api_key'][:8]}...masked"
        safe_config["bridges"].append(safe_bridge)
    
    return {"success": True, "configuration": safe_config}

@mcp.tool()
def reset_configuration() -> Dict[str, Any]:
    """
    Reset the MCP configuration (removes all bridges and settings).
    Use with caution - you'll need to reconfigure bridges.
    """
    logger.info("Resetting configuration")
    
    empty_config = {
        "bridges": [],
        "preferences": {
            "default_transition_time": 4,
            "color_temperature_range": [153, 500],
            "brightness_range": [1, 254],
            "preferred_color_mode": "natural"
        },
        "version": "2.0"
    }
    
    hue_config.save_config(empty_config)
    return {"success": True, "message": "Configuration reset successfully"}

@mcp.tool()
def update_preferences(preferences: Dict[str, Any]) -> Dict[str, Any]:
    """
    Update user preferences for the MCP server.
    
    Parameters:
    - preferences: Dictionary of preferences to update
    
    Available preferences:
    - default_transition_time: Default transition time in 100ms units
    - color_temperature_range: [min, max] Mired range
    - brightness_range: [min, max] brightness range
    - preferred_color_mode: "natural" or "technical"
    """
    logger.info(f"Updating preferences: {preferences}")
    
    try:
        hue_config.update_preferences(preferences)
        return {"success": True, "message": "Preferences updated successfully"}
    except Exception as e:
        logger.error(f"Error updating preferences: {e}")
        return {"success": False, "error": str(e)}

# ============================================================================
# BRIDGE INFO AND VALIDATION TOOLS
# ============================================================================

@mcp.tool()
def get_bridge_config() -> Dict[str, Any]:
    """
    Get the bridge configuration from the Philips Hue Bridge.
    """
    logger.info("Getting bridge configuration")
    
    base_url = hue_api.get_base_url()
    if not base_url:
        return {"success": False, "error": "No Hue Bridge configured"}
    
    try:
        response = requests.get(f"{base_url}/config", timeout=10)
        response.raise_for_status()
        return {"success": True, "config": response.json()}
    except requests.exceptions.RequestException as e:
        logger.error(f"Error getting bridge configuration: {e}")
        return {"success": False, "error": str(e)}


@mcp.tool()
def get_bridge_info(bridge_ip: str) -> Dict[str, Any]:
    """
    Get basic information about a bridge without authentication.
    
    Parameters:
    - bridge_ip: IP address of the bridge
    """
    logger.info(f"Getting bridge info for {bridge_ip}")
    return BridgeDiscovery.get_bridge_info(bridge_ip)


# ============================================================================
# UTILITY TOOLS
# ============================================================================

@mcp.tool()
def turn_all_lights_off() -> Dict[str, Any]:
    """
    Turn off all lights connected to the bridge.
    """
    logger.info("Turning off all lights")
    return hue_api.turn_all_lights_off()

@mcp.tool()
def turn_all_lights_on(brightness: Optional[int] = None) -> Dict[str, Any]:
    """
    Turn on all lights connected to the bridge.
    
    Parameters:
    - brightness: Optional brightness level (1-254)
    """
    logger.info("Turning on all lights")
    state = {"on": True}
    if brightness is not None:
        state["bri"] = max(1, min(254, brightness))
    
    return hue_api.set_group_state(0, state)


# ============================================================================
# RESOURCES
# ============================================================================

@mcp.resource("phillips-hue-server://setup-status")
def setup_status() -> str:
    """
    Get the current setup status of the MCP server.
    """
    logger.info("Getting setup status")
    
    bridges = hue_config.config.get("bridges", [])
    has_bridges = len(bridges) > 0
    
    status = {
        "configured": has_bridges,
        "bridge_count": len(bridges),
        "needs_setup": not has_bridges
    }
    
    if has_bridges:
        # Test connection to primary bridge
        connection_test = hue_api.test_connection()
        status["connection_status"] = connection_test
        status["primary_bridge"] = {
            "name": bridges[0]["name"],
            "ip": bridges[0]["ip"]
        }
    else:
        status["setup_instructions"] = [
            "1. Run quick_setup_workflow() to start",
            "2. Press your Hue bridge button",
            "3. Run setup_bridge(bridge_ip) with discovered IP"
        ]
    
    return json.dumps(status, indent=2)


if __name__ == "__main__":
    mcp.run()