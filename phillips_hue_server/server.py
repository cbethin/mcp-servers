# Philips Hue MCP server - CONSOLIDATED VERSION (12 tools)
import asyncio
import json
import logging
import os
import requests
from pathlib import Path
from typing import Dict, List, Optional, Any, Union
from mcp.server.fastmcp import FastMCP

# Import utilities
from utils import hue_api
from utils.config import hue_config, CONFIG_DIR
from utils.discovery import BridgeDiscovery
from utils.colors import ColorConverter
from utils.validation import HueValidator

# Configure logging
logging.basicConfig(
    level=logging.DEBUG if os.environ.get('DEBUG') else logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger("phillips_hue_server")

logger.info("=== Phillips Hue MCP Server Starting (Consolidated) ===")
logger.info(f"Debug mode: {'ON' if os.environ.get('DEBUG') else 'OFF'}")

# Create the MCP server instance
mcp = FastMCP(
    "phillips_hue_server", 
    instructions="""
     This is a consolidated Phillips Hue control server with 12 powerful tools.
     
     QUICK START:
     1. Run setup() to discover and configure your bridge
     2. Use control() to manage lights: control("Kitchen", color="warm white", brightness=200)
     3. Use scene() to apply scenes: scene("Relax", "Living Room")
     
     KEY TOOLS:
     - setup(): Complete bridge setup workflow
     - control(): Control any light or group with natural language
     - get_status(): Get info about lights, groups, or bridges
     - scene(): Apply Hue or custom scenes
     - transition(): Smooth light transitions
     
     TIPS:
     - Use natural color names: "sunset", "ocean", "warm white"
     - Target lights by name: "Kitchen", "Bedroom Lamp"
     - Target all lights: control("all", on=False)
    """
)

# Scene storage directory
SCENES_DIR = CONFIG_DIR / "scenes"
SCENES_DIR.mkdir(exist_ok=True)

# ============================================================================
# TOOL 1: SETUP (async) - Complete bridge discovery and setup
# ============================================================================

@mcp.async_tool()
async def setup(bridge_ip: Optional[str] = None):
    """
    Complete bridge setup workflow. Auto-discovers if no IP provided.
    
    Parameters:
    - bridge_ip: Optional IP address of bridge. If not provided, will auto-discover.
    
    Returns progress updates during setup process.
    """
    yield "🚀 Starting Phillips Hue setup..."
    
    # Check if already configured
    if hue_config.config.get("bridges") and not bridge_ip:
        test = hue_api.test_connection()
        if test["success"]:
            yield "✅ Bridge already configured and working!"
            yield f"Connected to: {hue_config.config['bridges'][0]['name']}"
            return
    
    # Discovery phase
    if not bridge_ip:
        yield "\n📡 Discovering bridges on your network..."
        bridges = BridgeDiscovery.discover_bridges()
        
        if not bridges:
            yield "❌ No bridges found. Please check:"
            yield "  - Bridge is powered on"
            yield "  - You're on the same network"
            yield "  - Try setup(bridge_ip='192.168.1.x') if you know the IP"
            return
        
        bridge = bridges[0]
        bridge_ip = bridge['ip']
        yield f"✅ Found bridge: {bridge['name']} at {bridge_ip}"
    else:
        # Verify it's a bridge
        bridge_info = BridgeDiscovery.get_bridge_info(bridge_ip)
        if not bridge_info["success"]:
            yield f"❌ {bridge_ip} is not a Hue bridge"
            return
        yield f"✅ Found bridge at {bridge_ip}"
    
    # Setup phase
    yield "\n🔘 Press the button on your Hue bridge NOW!"
    yield "⏳ Waiting for button press..."
    
    max_attempts = 30
    for attempt in range(max_attempts):
        result = BridgeDiscovery.create_api_key(bridge_ip)
        
        if result["success"]:
            bridge_id = hue_config.add_bridge(
                bridge_ip, 
                result["api_key"], 
                result.get("bridge_name", "Philips Hue Bridge")
            )
            yield f"\n✅ Success! Bridge configured with ID: {bridge_id}"
            yield "🎉 You can now control your lights!"
            return
        
        if attempt % 5 == 0:
            yield f"⏳ Still waiting... ({attempt}/{max_attempts})"
        
        await asyncio.sleep(1)
    
    yield "❌ Setup timeout. Please try again."

# ============================================================================
# TOOL 2: CONTROL - Universal light/group control
# ============================================================================

@mcp.tool()
def control(
    target: str = "all",
    color: Optional[str] = None,
    brightness: Optional[int] = None,
    on: Optional[bool] = None
) -> Dict[str, Any]:
    """
    Control any light or group with natural language.
    
    Parameters:
    - target: Light/group name or "all" for all lights
    - color: Natural color name (e.g., "sunset", "warm white", "#FF5500")
    - brightness: 1-254 (optional)
    - on: True/False to turn on/off (optional)
    
    Examples:
    - control("all", on=False)  # Turn off all lights
    - control("Kitchen", color="warm white", brightness=200)
    - control("Living Room", color="sunset")
    """
    logger.info(f"Control request: target={target}, color={color}, brightness={brightness}, on={on}")
    
    # Build state
    state = {}
    
    if on is not None:
        state["on"] = on
    
    if color and on is not False:  # Don't set color when turning off
        state.update(ColorConverter.parse_color(color))
        state["on"] = True  # Turn on when setting color
    
    if brightness is not None and on is not False:
        state["bri"] = max(1, min(254, brightness))
        state["on"] = True  # Turn on when setting brightness
    
    if not state:
        return {"success": False, "error": "No changes specified"}
    
    # Handle "all" target
    if target.lower() == "all":
        results = []
        lights = hue_api.get_all_lights()
        
        for light_id in lights:
            result = hue_api.set_light_state(light_id, state)
            results.append({"light": lights[light_id]["name"], "success": result["success"]})
        
        return {
            "success": True,
            "lights_updated": len([r for r in results if r["success"]]),
            "total_lights": len(results),
            "state_applied": state
        }
    
    # Try as group first
    try:
        groups = hue_api.get_all_groups()
        group_match = None
        
        for group_id, group_data in groups.items():
            if group_data["name"].lower() == target.lower():
                group_match = group_id
                break
        
        if group_match:
            result = hue_api.set_group_state(group_match, state)
            return {
                "success": result["success"],
                "type": "group",
                "name": groups[group_match]["name"],
                "lights_in_group": len(groups[group_match].get("lights", [])),
                "state_applied": state
            }
    except:
        pass
    
    # Try as light
    try:
        light_id = hue_api.parse_identifier(target, "lights")
        result = hue_api.set_light_state(light_id, state)
        
        if result["success"]:
            light_info = hue_api.get_light(light_id)
            return {
                "success": True,
                "type": "light",
                "name": light_info["name"],
                "state_applied": state
            }
        else:
            return result
    except Exception as e:
        return {"success": False, "error": f"Target '{target}' not found as light or group"}

# ============================================================================
# TOOL 3: GET_STATUS - Get info about lights, groups, or bridges
# ============================================================================

@mcp.tool()
def get_status(resource: str = "all", id: Optional[str] = None) -> Dict[str, Any]:
    """
    Get status information about lights, groups, or bridges.
    
    Parameters:
    - resource: "lights", "groups", "bridges", or "all"
    - id: Optional specific light/group name or ID
    
    Examples:
    - get_status("lights")  # All lights
    - get_status("groups", "Living Room")  # Specific group
    - get_status("all")  # Everything
    """
    logger.info(f"Status request: resource={resource}, id={id}")
    
    if resource == "bridges":
        bridges = hue_config.config.get("bridges", [])
        if not bridges:
            return {"success": False, "error": "No bridges configured"}
        
        # Test connections
        results = []
        for bridge in bridges:
            test = hue_api.test_connection()
            results.append({
                "name": bridge["name"],
                "ip": bridge["ip"],
                "connected": test["success"],
                "error": test.get("error") if not test["success"] else None
            })
        
        return {"success": True, "bridges": results}
    
    elif resource == "lights" or (resource == "all" and not id):
        if id:
            try:
                light_id = hue_api.parse_identifier(id, "lights")
                light = hue_api.get_light(light_id)
                return {
                    "success": True,
                    "light": {
                        "id": light_id,
                        "name": light["name"],
                        "on": light["state"]["on"],
                        "brightness": light["state"].get("bri"),
                        "reachable": light["state"]["reachable"]
                    }
                }
            except Exception as e:
                return {"success": False, "error": str(e)}
        else:
            lights = hue_api.get_all_lights()
            light_list = []
            for light_id, light_data in lights.items():
                light_list.append({
                    "id": light_id,
                    "name": light_data["name"],
                    "on": light_data["state"]["on"],
                    "brightness": light_data["state"].get("bri"),
                    "reachable": light_data["state"]["reachable"]
                })
            return {"success": True, "lights": light_list}
    
    elif resource == "groups" or (resource == "all" and not id):
        if id:
            try:
                groups = hue_api.get_all_groups()
                group_match = None
                
                for group_id, group_data in groups.items():
                    if group_data["name"].lower() == id.lower() or group_id == id:
                        group_match = group_id
                        break
                
                if group_match:
                    group = groups[group_match]
                    return {
                        "success": True,
                        "group": {
                            "id": group_match,
                            "name": group["name"],
                            "lights": group.get("lights", []),
                            "on": group["state"]["all_on"],
                            "any_on": group["state"]["any_on"]
                        }
                    }
                else:
                    return {"success": False, "error": f"Group '{id}' not found"}
            except Exception as e:
                return {"success": False, "error": str(e)}
        else:
            groups = hue_api.get_all_groups()
            group_list = []
            for group_id, group_data in groups.items():
                group_list.append({
                    "id": group_id,
                    "name": group_data["name"],
                    "lights": len(group_data.get("lights", [])),
                    "on": group_data["state"]["all_on"],
                    "any_on": group_data["state"]["any_on"]
                })
            return {"success": True, "groups": group_list}
    
    elif resource == "all":
        # Return everything
        result = {"success": True}
        
        # Add bridges
        bridges = get_status("bridges")
        if bridges["success"]:
            result["bridges"] = bridges.get("bridges", [])
        
        # Add lights
        lights = get_status("lights")
        if lights["success"]:
            result["lights"] = lights.get("lights", [])
        
        # Add groups
        groups = get_status("groups")
        if groups["success"]:
            result["groups"] = groups.get("groups", [])
        
        return result
    
    else:
        return {"success": False, "error": f"Invalid resource type: {resource}"}

# ============================================================================
# TOOL 4: SCENE (async) - Apply scenes
# ============================================================================

@mcp.async_tool()
async def scene(
    name: str,
    target: Optional[str] = None,
    transition_time: Optional[int] = None
):
    """
    Apply a scene to lights or groups.
    
    Parameters:
    - name: Scene name (Hue scene or saved custom scene)
    - target: Group name or "all" (defaults to scene's target)
    - transition_time: Transition time in seconds
    
    Examples:
    - scene("Relax", "Living Room")
    - scene("sunset_mood")  # Custom saved scene
    """
    yield f"🎨 Applying scene '{name}'..."
    
    # Check if it's a saved custom scene
    scene_file = SCENES_DIR / f"{name}.json"
    if scene_file.exists():
        yield "📂 Loading custom scene..."
        
        with open(scene_file, 'r') as f:
            scene_data = json.load(f)
        
        lights_config = scene_data.get("lights", {})
        total_lights = len(lights_config)
        completed = 0
        
        for light_name, state in lights_config.items():
            try:
                light_id = hue_api.parse_identifier(light_name, "lights")
                
                if transition_time:
                    state["transitiontime"] = transition_time * 10
                
                hue_api.set_light_state(light_id, state)
                completed += 1
                
                progress = int((completed / total_lights) * 100)
                yield f"Progress: {progress}% - Set {light_name}"
                
            except Exception as e:
                yield f"⚠️ Failed to set {light_name}: {e}"
            
            await asyncio.sleep(0.1)
        
        yield f"✅ Custom scene applied to {completed}/{total_lights} lights"
        return
    
    # Try as Hue scene
    yield "🔍 Searching for Hue scene..."
    
    scenes = hue_api.get_scenes()
    scene_match = None
    
    for scene_id, scene_data in scenes.items():
        if scene_data["name"].lower() == name.lower():
            scene_match = scene_id
            break
    
    if not scene_match:
        yield f"❌ Scene '{name}' not found"
        yield "💡 Use manage_scenes() to list available scenes"
        return
    
    # Determine target group
    if target and target.lower() != "all":
        groups = hue_api.get_all_groups()
        group_id = None
        
        for gid, gdata in groups.items():
            if gdata["name"].lower() == target.lower():
                group_id = gid
                break
        
        if not group_id:
            yield f"❌ Group '{target}' not found"
            return
    else:
        # Use scene's default group
        group_id = scenes[scene_match].get("group", "0")
    
    # Apply scene
    result = hue_api.activate_scene(group_id, scene_match)
    
    if result["success"]:
        yield f"✅ Scene '{name}' applied successfully"
    else:
        yield f"❌ Failed to apply scene: {result.get('error')}"

# ============================================================================
# TOOL 5: SAVE_SCENE - Save current lighting as scene
# ============================================================================

@mcp.tool()
def save_scene(name: str, notes: Optional[str] = None) -> Dict[str, Any]:
    """
    Save current lighting state as a custom scene.
    
    Parameters:
    - name: Scene name (alphanumeric and underscores only)
    - notes: Optional description
    """
    if not name or not name.replace("_", "").isalnum():
        return {"success": False, "error": "Scene name must be alphanumeric (underscores allowed)"}
    
    # Get current state of all lights
    lights = hue_api.get_all_lights()
    scene_data = {
        "name": name,
        "notes": notes,
        "lights": {}
    }
    
    for light_id, light_data in lights.items():
        if light_data["state"]["on"]:
            state = {
                "on": True,
                "bri": light_data["state"].get("bri", 254)
            }
            
            # Add color if available
            if "xy" in light_data["state"]:
                state["xy"] = light_data["state"]["xy"]
            elif "ct" in light_data["state"]:
                state["ct"] = light_data["state"]["ct"]
            
            scene_data["lights"][light_data["name"]] = state
    
    # Save to file
    scene_file = SCENES_DIR / f"{name}.json"
    with open(scene_file, 'w') as f:
        json.dump(scene_data, f, indent=2)
    
    return {
        "success": True,
        "message": f"Scene '{name}' saved with {len(scene_data['lights'])} lights",
        "lights_saved": list(scene_data["lights"].keys())
    }

# ============================================================================
# TOOL 6: MANAGE_SCENES - List and manage scenes
# ============================================================================

@mcp.tool()
def manage_scenes(action: str = "list", scene_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Manage Hue and custom scenes.
    
    Parameters:
    - action: "list", "delete", or "info"
    - scene_id: Scene name/ID for delete or info actions
    
    Examples:
    - manage_scenes("list")
    - manage_scenes("delete", "sunset_mood")
    - manage_scenes("info", "Relax")
    """
    if action == "list":
        result = {"success": True, "hue_scenes": [], "custom_scenes": []}
        
        # Get Hue scenes
        scenes = hue_api.get_scenes()
        for scene_id, scene_data in scenes.items():
            result["hue_scenes"].append({
                "id": scene_id,
                "name": scene_data["name"],
                "type": scene_data.get("type", "Unknown")
            })
        
        # Get custom scenes
        for scene_file in SCENES_DIR.glob("*.json"):
            try:
                with open(scene_file, 'r') as f:
                    scene_data = json.load(f)
                result["custom_scenes"].append({
                    "name": scene_file.stem,
                    "notes": scene_data.get("notes", ""),
                    "lights": len(scene_data.get("lights", {}))
                })
            except:
                pass
        
        return result
    
    elif action == "delete" and scene_id:
        # Only delete custom scenes
        scene_file = SCENES_DIR / f"{scene_id}.json"
        if scene_file.exists():
            scene_file.unlink()
            return {"success": True, "message": f"Deleted custom scene '{scene_id}'"}
        else:
            return {"success": False, "error": f"Custom scene '{scene_id}' not found"}
    
    elif action == "info" and scene_id:
        # Check custom scenes first
        scene_file = SCENES_DIR / f"{scene_id}.json"
        if scene_file.exists():
            with open(scene_file, 'r') as f:
                scene_data = json.load(f)
            return {
                "success": True,
                "type": "custom",
                "name": scene_data["name"],
                "notes": scene_data.get("notes"),
                "lights": scene_data.get("lights", {})
            }
        
        # Check Hue scenes
        scenes = hue_api.get_scenes()
        for sid, sdata in scenes.items():
            if sdata["name"].lower() == scene_id.lower() or sid == scene_id:
                return {
                    "success": True,
                    "type": "hue",
                    "id": sid,
                    "name": sdata["name"],
                    "lights": sdata.get("lights", [])
                }
        
        return {"success": False, "error": f"Scene '{scene_id}' not found"}
    
    else:
        return {"success": False, "error": f"Invalid action: {action}"}

# ============================================================================
# TOOL 7: TRANSITION (async) - Smooth light transitions
# ============================================================================

@mcp.async_tool()
async def transition(
    target: str,
    to_color: str,
    duration: int = 5,
    from_color: Optional[str] = None
):
    """
    Smoothly transition lights between colors.
    
    Parameters:
    - target: Light/group name or "all"
    - to_color: Target color (natural language)
    - duration: Transition duration in seconds
    - from_color: Starting color (uses current if not specified)
    
    Examples:
    - transition("Living Room", "sunset", 10)
    - transition("all", "warm white", 30, from_color="daylight")
    """
    yield f"🔄 Starting {duration}s transition to {to_color}..."
    
    # Parse target
    lights = []
    if target.lower() == "all":
        all_lights = hue_api.get_all_lights()
        lights = list(all_lights.keys())
    else:
        # Try as group first
        groups = hue_api.get_all_groups()
        for gid, gdata in groups.items():
            if gdata["name"].lower() == target.lower():
                lights = gdata.get("lights", [])
                break
        
        # Try as single light
        if not lights:
            try:
                light_id = hue_api.parse_identifier(target, "lights")
                lights = [str(light_id)]
            except:
                yield f"❌ Target '{target}' not found"
                return
    
    if not lights:
        yield "❌ No lights found for target"
        return
    
    # Parse colors
    end_state = ColorConverter.parse_color(to_color)
    end_state["on"] = True
    
    # Use Hue's built-in transition
    transition_time = duration * 10  # Convert to deciseconds
    end_state["transitiontime"] = transition_time
    
    # Apply to all lights
    for light_id in lights:
        try:
            hue_api.set_light_state(light_id, end_state)
        except Exception as e:
            yield f"⚠️ Failed to transition light {light_id}: {e}"
    
    yield f"✅ Transition started for {len(lights)} light(s)"
    
    # Show progress
    steps = min(duration, 10)  # Max 10 updates
    step_duration = duration / steps
    
    for i in range(steps):
        await asyncio.sleep(step_duration)
        progress = int(((i + 1) / steps) * 100)
        yield f"Progress: {progress}%"
    
    yield "✅ Transition complete!"

# ============================================================================
# TOOL 8: BRIDGE - Bridge management utilities
# ============================================================================

@mcp.tool()
def bridge(action: str = "status") -> Dict[str, Any]:
    """
    Bridge management utilities.
    
    Parameters:
    - action: "status", "test", "info", or "config"
    
    Examples:
    - bridge("status")  # Quick status check
    - bridge("test")    # Test connection
    - bridge("config")  # Get bridge configuration
    """
    if action == "status":
        bridges = hue_config.config.get("bridges", [])
        if not bridges:
            return {"success": False, "error": "No bridges configured", "hint": "Run setup() first"}
        
        bridge = bridges[0]
        test = hue_api.test_connection()
        
        return {
            "success": True,
            "configured": True,
            "name": bridge["name"],
            "ip": bridge["ip"],
            "connected": test["success"],
            "error": test.get("error") if not test["success"] else None
        }
    
    elif action == "test":
        return hue_api.test_connection()
    
    elif action == "info":
        if not hue_config.config.get("bridges"):
            return {"success": False, "error": "No bridge configured"}
        
        bridge_ip = hue_config.config["bridges"][0]["ip"]
        return BridgeDiscovery.get_bridge_info(bridge_ip)
    
    elif action == "config":
        config = hue_api.get_bridge_config()
        if config:
            return {
                "success": True,
                "bridge_name": config.get("name"),
                "api_version": config.get("apiversion"),
                "software_version": config.get("swversion"),
                "zigbee_channel": config.get("zigbeechannel"),
                "ip_address": config.get("ipaddress"),
                "mac_address": config.get("mac")
            }
        else:
            return {"success": False, "error": "Failed to get bridge config"}
    
    else:
        return {"success": False, "error": f"Invalid action: {action}"}

# ============================================================================
# TOOL 9: GROUPS - Create and manage light groups
# ============================================================================

@mcp.tool()
def groups(
    action: str,
    name: Optional[str] = None,
    lights: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    Create or delete light groups.
    
    Parameters:
    - action: "create" or "delete"
    - name: Group name
    - lights: List of light names/IDs (for create action)
    
    Examples:
    - groups("create", "Bedroom", ["Lamp 1", "Lamp 2"])
    - groups("delete", "Bedroom")
    """
    if action == "create":
        if not name or not lights:
            return {"success": False, "error": "Name and lights required for create action"}
        
        # Convert light names to IDs
        light_ids = []
        for light in lights:
            try:
                light_id = hue_api.parse_identifier(light, "lights")
                light_ids.append(str(light_id))
            except Exception as e:
                return {"success": False, "error": f"Light '{light}' not found"}
        
        result = hue_api.create_group(name, light_ids)
        return result
    
    elif action == "delete":
        if not name:
            return {"success": False, "error": "Name required for delete action"}
        
        # Find group by name
        groups = hue_api.get_all_groups()
        group_id = None
        
        for gid, gdata in groups.items():
            if gdata["name"].lower() == name.lower():
                group_id = gid
                break
        
        if not group_id:
            return {"success": False, "error": f"Group '{name}' not found"}
        
        result = hue_api.delete_group(group_id)
        return result
    
    else:
        return {"success": False, "error": f"Invalid action: {action}"}

# ============================================================================
# TOOL 10: CONFIG - Configuration management
# ============================================================================

@mcp.tool()
def config(action: str = "show", settings: Optional[Dict] = None) -> Dict[str, Any]:
    """
    Manage Phillips Hue MCP configuration.
    
    Parameters:
    - action: "show", "reset", or "update"
    - settings: Configuration settings (for update action)
    
    Examples:
    - config("show")
    - config("reset")
    - config("update", {"default_transition": 2})
    """
    if action == "show":
        return {
            "success": True,
            "configuration": {
                "bridges": len(hue_config.config.get("bridges", [])),
                "preferences": hue_config.config.get("preferences", {}),
                "config_file": str(hue_config.config_file)
            }
        }
    
    elif action == "reset":
        hue_config.config = {"bridges": [], "preferences": {}}
        hue_config.save_config()
        return {"success": True, "message": "Configuration reset. Run setup() to reconfigure."}
    
    elif action == "update":
        if not settings:
            return {"success": False, "error": "Settings required for update action"}
        
        if "preferences" not in hue_config.config:
            hue_config.config["preferences"] = {}
        
        hue_config.config["preferences"].update(settings)
        hue_config.save_config()
        
        return {
            "success": True,
            "message": "Preferences updated",
            "preferences": hue_config.config["preferences"]
        }
    
    else:
        return {"success": False, "error": f"Invalid action: {action}"}

# ============================================================================
# TOOL 11: COLORS - Color utilities
# ============================================================================

@mcp.tool()
def colors(query: Optional[str] = None) -> Dict[str, Any]:
    """
    Get available colors or suggestions for a query.
    
    Parameters:
    - query: Optional color to get suggestions for
    
    Examples:
    - colors()  # List all available colors
    - colors("sunset")  # Get similar colors
    """
    if not query:
        # Return all available colors
        return {
            "success": True,
            "color_categories": {
                "temperature_presets": [
                    "candle", "warm_white", "soft_white", "daylight", 
                    "cool_white", "moonlight"
                ],
                "nature_colors": [
                    "sunset", "sunrise", "ocean", "forest", "autumn",
                    "spring", "summer", "winter"
                ],
                "basic_colors": [
                    "red", "green", "blue", "yellow", "purple", "orange",
                    "pink", "cyan", "magenta", "white"
                ],
                "mood_colors": [
                    "relax", "energize", "focus", "romance", "party",
                    "meditation", "sleep", "wake"
                ]
            },
            "tip": "You can also use hex codes like #FF5500"
        }
    
    else:
        # Get suggestions
        suggestions = []
        
        # Check if it's already valid
        try:
            ColorConverter.parse_color(query)
            return {
                "success": True,
                "query": query,
                "valid": True,
                "message": f"'{query}' is a valid color"
            }
        except:
            pass
        
        # Find similar colors
        all_colors = [
            "candle", "warm_white", "soft_white", "daylight", "cool_white",
            "sunset", "sunrise", "ocean", "forest", "autumn",
            "red", "green", "blue", "yellow", "purple", "orange",
            "pink", "cyan", "magenta", "relax", "energize", "focus"
        ]
        
        query_lower = query.lower()
        
        # Exact matches
        for color in all_colors:
            if query_lower in color or color in query_lower:
                suggestions.append(color)
        
        # Fuzzy matches
        if not suggestions:
            for color in all_colors:
                if any(c in query_lower for c in color.split('_')):
                    suggestions.append(color)
        
        return {
            "success": True,
            "query": query,
            "valid": False,
            "suggestions": suggestions[:5] if suggestions else ["Try: warm_white, sunset, ocean, red, blue"],
            "tip": "Use colors() without arguments to see all available colors"
        }

# ============================================================================
# TOOL 12: TEST (async) - Simple test tool
# ============================================================================

@mcp.async_tool()
async def test():
    """Test async functionality."""
    yield "🧪 Testing Phillips Hue MCP server..."
    
    # Test configuration
    yield "1️⃣ Checking configuration..."
    if hue_config.config.get("bridges"):
        yield "✅ Bridge configured"
    else:
        yield "⚠️ No bridge configured - run setup() first"
        return
    
    # Test connection
    yield "2️⃣ Testing connection..."
    test_result = hue_api.test_connection()
    if test_result["success"]:
        yield "✅ Connected to bridge"
    else:
        yield f"❌ Connection failed: {test_result.get('error')}"
        return
    
    # Test light control
    yield "3️⃣ Testing light discovery..."
    lights = hue_api.get_all_lights()
    yield f"✅ Found {len(lights)} lights"
    
    await asyncio.sleep(1)
    yield "✅ All tests passed!"

# ============================================================================
# RESOURCE: Setup status
# ============================================================================

@mcp.resource("phillips-hue-server://setup-status")
def get_setup_status() -> str:
    """Get current setup status of the Phillips Hue server."""
    if not hue_config.config.get("bridges"):
        return json.dumps({
            "configured": False,
            "message": "No bridges configured. Run setup() to get started."
        }, indent=2)
    
    bridge = hue_config.config["bridges"][0]
    test = hue_api.test_connection()
    
    return json.dumps({
        "configured": True,
        "bridge_name": bridge["name"],
        "bridge_ip": bridge["ip"],
        "connected": test["success"],
        "error": test.get("error") if not test["success"] else None,
        "message": "Ready to control lights!" if test["success"] else "Bridge not reachable"
    }, indent=2)

# Export the server instance
if __name__ == "__main__":
    mcp.run()