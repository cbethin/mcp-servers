"""
Parameter validation utilities for Philips Hue API.
Ensures API calls use valid parameters within Hue's constraints.
"""

import logging
from typing import Dict, Any, Optional, Union, List

logger = logging.getLogger("validation")

# Hue API parameter constraints
CONSTRAINTS = {
    "brightness": {"min": 1, "max": 254, "key": "bri"},
    "saturation": {"min": 0, "max": 254, "key": "sat"},
    "hue": {"min": 0, "max": 65535, "key": "hue"},
    "color_temperature": {"min": 153, "max": 500, "key": "ct"},  # In mireds
    "transition_time": {"min": 0, "max": 65535, "key": "transitiontime"},  # In deciseconds
    "alert": {"values": ["none", "select", "lselect"], "key": "alert"},
    "effect": {"values": ["none", "colorloop"], "key": "effect"},
    "xy": {"x_range": [0.0, 1.0], "y_range": [0.0, 1.0], "key": "xy"}
}

# Valid state keys for different operations
LIGHT_STATE_KEYS = {
    "on", "bri", "hue", "sat", "xy", "ct", "alert", "effect", 
    "transitiontime", "bri_inc", "sat_inc", "hue_inc", "ct_inc", "xy_inc"
}

GROUP_STATE_KEYS = LIGHT_STATE_KEYS  # Groups support same state keys

SCENE_KEYS = {"name", "lights", "recycle", "type", "group", "picture"}


class HueValidator:
    """Validate parameters for Philips Hue API calls."""
    
    @staticmethod
    def validate_brightness(value: int) -> Optional[int]:
        """Validate brightness value (1-254)."""
        if value is None:
            return None
        try:
            val = int(value)
            return max(CONSTRAINTS["brightness"]["min"], 
                      min(CONSTRAINTS["brightness"]["max"], val))
        except (ValueError, TypeError):
            logger.warning(f"Invalid brightness value: {value}")
            return None
    
    @staticmethod
    def validate_color_temperature(value: int) -> Optional[int]:
        """Validate color temperature in mireds (153-500)."""
        if value is None:
            return None
        try:
            val = int(value)
            return max(CONSTRAINTS["color_temperature"]["min"], 
                      min(CONSTRAINTS["color_temperature"]["max"], val))
        except (ValueError, TypeError):
            logger.warning(f"Invalid color temperature value: {value}")
            return None
    
    @staticmethod
    def validate_xy(xy: List[float]) -> Optional[List[float]]:
        """Validate xy color coordinates."""
        if not isinstance(xy, list) or len(xy) != 2:
            logger.warning(f"Invalid xy format: {xy}")
            return None
        
        try:
            x = float(xy[0])
            y = float(xy[1])
            
            # Clamp to valid range
            x = max(0.0, min(1.0, x))
            y = max(0.0, min(1.0, y))
            
            return [round(x, 4), round(y, 4)]
        except (ValueError, TypeError):
            logger.warning(f"Invalid xy values: {xy}")
            return None
    
    @staticmethod
    def validate_transition_time(value: Union[int, float]) -> Optional[int]:
        """Validate transition time (in deciseconds)."""
        if value is None:
            return None
        try:
            # Convert seconds to deciseconds if needed
            if isinstance(value, float) and value < 100:
                val = int(value * 10)  # Assume seconds, convert to deciseconds
            else:
                val = int(value)
            
            return max(CONSTRAINTS["transition_time"]["min"], 
                      min(CONSTRAINTS["transition_time"]["max"], val))
        except (ValueError, TypeError):
            logger.warning(f"Invalid transition time: {value}")
            return None
    
    @staticmethod
    def clean_light_state(state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Clean and validate a light state dictionary.
        Removes invalid keys and validates values.
        """
        cleaned = {}
        
        for key, value in state.items():
            # Skip invalid keys
            if key not in LIGHT_STATE_KEYS:
                logger.debug(f"Skipping invalid state key: {key}")
                continue
            
            # Validate specific parameters
            if key == "bri":
                validated = HueValidator.validate_brightness(value)
                if validated is not None:
                    cleaned[key] = validated
            
            elif key == "ct":
                validated = HueValidator.validate_color_temperature(value)
                if validated is not None:
                    cleaned[key] = validated
            
            elif key == "xy":
                validated = HueValidator.validate_xy(value)
                if validated is not None:
                    cleaned[key] = validated
            
            elif key == "transitiontime":
                validated = HueValidator.validate_transition_time(value)
                if validated is not None:
                    cleaned[key] = validated
            
            elif key == "sat":
                try:
                    cleaned[key] = max(0, min(254, int(value)))
                except:
                    logger.warning(f"Invalid saturation value: {value}")
            
            elif key == "hue":
                try:
                    cleaned[key] = max(0, min(65535, int(value)))
                except:
                    logger.warning(f"Invalid hue value: {value}")
            
            elif key == "on":
                cleaned[key] = bool(value)
            
            elif key == "alert":
                if value in CONSTRAINTS["alert"]["values"]:
                    cleaned[key] = value
                else:
                    logger.warning(f"Invalid alert value: {value}")
            
            elif key == "effect":
                if value in CONSTRAINTS["effect"]["values"]:
                    cleaned[key] = value
                else:
                    logger.warning(f"Invalid effect value: {value}")
            
            elif key.endswith("_inc"):
                # Increment values
                try:
                    cleaned[key] = int(value)
                except:
                    logger.warning(f"Invalid increment value for {key}: {value}")
            
            else:
                # Pass through other valid keys
                cleaned[key] = value
        
        # Color mode validation
        HueValidator._validate_color_mode(cleaned)
        
        return cleaned
    
    @staticmethod
    def _validate_color_mode(state: Dict[str, Any]) -> None:
        """
        Ensure only one color mode is specified.
        Priority: xy > ct > hue/sat
        """
        if "xy" in state:
            # Remove other color modes if xy is present
            state.pop("ct", None)
            state.pop("hue", None)
            state.pop("sat", None)
        elif "ct" in state:
            # Remove hue/sat if ct is present
            state.pop("hue", None)
            state.pop("sat", None)
    
    @staticmethod
    def validate_group_action(action: Dict[str, Any]) -> Dict[str, Any]:
        """Validate group action parameters."""
        # Groups use same validation as lights
        return HueValidator.clean_light_state(action)
    
    @staticmethod
    def validate_scene_data(scene: Dict[str, Any]) -> Dict[str, Any]:
        """Validate scene creation parameters."""
        cleaned = {}
        
        for key, value in scene.items():
            if key not in SCENE_KEYS:
                logger.debug(f"Skipping invalid scene key: {key}")
                continue
            
            if key == "name" and isinstance(value, str):
                # Scene names have max length
                cleaned[key] = value[:32]
            elif key == "lights" and isinstance(value, list):
                # Ensure lights are strings
                cleaned[key] = [str(light) for light in value]
            elif key == "recycle":
                cleaned[key] = bool(value)
            else:
                cleaned[key] = value
        
        return cleaned
    
    @staticmethod
    def get_validation_info() -> Dict[str, Any]:
        """Get information about valid parameter ranges."""
        return {
            "brightness": {
                "range": [CONSTRAINTS["brightness"]["min"], CONSTRAINTS["brightness"]["max"]],
                "description": "Light brightness level"
            },
            "color_temperature": {
                "range": [CONSTRAINTS["color_temperature"]["min"], CONSTRAINTS["color_temperature"]["max"]],
                "unit": "mireds",
                "description": "Color temperature (153=6500K cool, 500=2000K warm)"
            },
            "saturation": {
                "range": [CONSTRAINTS["saturation"]["min"], CONSTRAINTS["saturation"]["max"]],
                "description": "Color saturation"
            },
            "hue": {
                "range": [CONSTRAINTS["hue"]["min"], CONSTRAINTS["hue"]["max"]],
                "description": "Color hue value"
            },
            "xy": {
                "format": "[x, y]",
                "range": "x: 0.0-1.0, y: 0.0-1.0",
                "description": "CIE xy color coordinates"
            },
            "transition_time": {
                "range": [CONSTRAINTS["transition_time"]["min"], CONSTRAINTS["transition_time"]["max"]],
                "unit": "deciseconds (0.1 second)",
                "description": "Transition duration"
            },
            "alert": {
                "values": CONSTRAINTS["alert"]["values"],
                "description": "Alert effect"
            },
            "effect": {
                "values": CONSTRAINTS["effect"]["values"],
                "description": "Dynamic effect"
            }
        }