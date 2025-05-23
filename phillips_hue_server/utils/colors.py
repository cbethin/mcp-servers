"""
Color conversion utilities for Philips Hue.
Handles natural language color names, hex codes, and color temperature presets.
"""

import logging
import re
from typing import Dict, Any, Optional, List, Tuple

logger = logging.getLogger("colors")

# Color definitions with xy coordinates for Hue
COLOR_DEFINITIONS = {
    # Basic colors
    "red": {"xy": [0.6484, 0.3309], "bri": 254},
    "green": {"xy": [0.3144, 0.6279], "bri": 254},
    "blue": {"xy": [0.1691, 0.0441], "bri": 254},
    "yellow": {"xy": [0.4432, 0.5154], "bri": 254},
    "orange": {"xy": [0.5614, 0.4156], "bri": 254},
    "purple": {"xy": [0.2725, 0.1096], "bri": 254},
    "pink": {"xy": [0.4149, 0.1776], "bri": 254},
    "cyan": {"xy": [0.1727, 0.3672], "bri": 254},
    "magenta": {"xy": [0.3824, 0.1601], "bri": 254},
    "white": {"xy": [0.3227, 0.3290], "bri": 254},
    
    # Natural scenes
    "sunset": {"xy": [0.5614, 0.4156], "bri": 200},
    "sunrise": {"xy": [0.4432, 0.5154], "bri": 180},
    "ocean": {"xy": [0.1691, 0.3441], "bri": 150},
    "forest": {"xy": [0.2144, 0.5279], "bri": 150},
    "fire": {"xy": [0.6484, 0.3309], "bri": 220},
    "lavender": {"xy": [0.3085, 0.1540], "bri": 180},
    
    # Warm/cool variations
    "warm_white": {"ct": 500, "bri": 254},  # 2000K
    "soft_white": {"ct": 380, "bri": 254},  # 2700K
    "neutral_white": {"ct": 250, "bri": 254},  # 4000K
    "cool_white": {"ct": 200, "bri": 254},  # 5000K
    "daylight": {"ct": 153, "bri": 254},  # 6500K
    "candle": {"ct": 500, "bri": 150},  # 2000K dim
    "moonlight": {"xy": [0.3227, 0.3290], "bri": 50},
    
    # Extended colors
    "amber": {"xy": [0.5614, 0.4156], "bri": 254},
    "turquoise": {"xy": [0.1727, 0.3672], "bri": 200},
    "coral": {"xy": [0.5075, 0.3145], "bri": 200},
    "lime": {"xy": [0.3532, 0.5686], "bri": 254},
    "indigo": {"xy": [0.2332, 0.0975], "bri": 180},
    "teal": {"xy": [0.1700, 0.3487], "bri": 200},
    "gold": {"xy": [0.4947, 0.4619], "bri": 254},
    "silver": {"xy": [0.3227, 0.3290], "bri": 180},
    "bronze": {"xy": [0.4746, 0.3814], "bri": 180},
}

# Aliases for common variations
COLOR_ALIASES = {
    "warm": "warm_white",
    "cool": "cool_white",
    "soft": "soft_white",
    "bright": "daylight",
    "dim": "candle",
    "relax": "warm_white",
    "concentrate": "cool_white",
    "energize": "daylight",
    "sleep": "candle",
    "reading": "neutral_white",
    "evening": "soft_white",
    "morning": "daylight",
    "night": "moonlight",
}


class ColorConverter:
    """Convert between different color representations for Philips Hue."""
    
    @staticmethod
    def parse_color(color_input: str) -> Dict[str, Any]:
        """
        Parse a color input string and return Hue-compatible state.
        
        Supports:
        - Named colors: "red", "warm white", "sunset"
        - Hex codes: "#FF5500", "FF5500"
        - RGB values: "rgb(255,85,0)"
        - Color temperatures: "2700K", "5000K"
        
        Returns dict with xy/ct coordinates and brightness.
        """
        color_input = color_input.lower().strip()
        
        # Check direct color definitions
        if color_input in COLOR_DEFINITIONS:
            return COLOR_DEFINITIONS[color_input].copy()
        
        # Check aliases
        if color_input in COLOR_ALIASES:
            return COLOR_DEFINITIONS[COLOR_ALIASES[color_input]].copy()
        
        # Check for hex color
        hex_match = re.match(r'^#?([0-9a-f]{6})$', color_input)
        if hex_match:
            return ColorConverter._hex_to_xy(hex_match.group(1))
        
        # Check for RGB format
        rgb_match = re.match(r'^rgb\s*\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*\)$', color_input)
        if rgb_match:
            r, g, b = map(int, rgb_match.groups())
            return ColorConverter._rgb_to_xy(r, g, b)
        
        # Check for Kelvin temperature
        kelvin_match = re.match(r'^(\d+)k$', color_input)
        if kelvin_match:
            kelvin = int(kelvin_match.group(1))
            return ColorConverter._kelvin_to_mired(kelvin)
        
        # Try fuzzy matching
        for key in COLOR_DEFINITIONS:
            if key in color_input or color_input in key:
                logger.info(f"Fuzzy matched '{color_input}' to '{key}'")
                return COLOR_DEFINITIONS[key].copy()
        
        # Default to neutral white if no match
        logger.warning(f"Color '{color_input}' not recognized, using neutral white")
        return {"xy": [0.3227, 0.3290], "bri": 254}
    
    @staticmethod
    def _hex_to_xy(hex_color: str) -> Dict[str, Any]:
        """Convert hex color to xy coordinates."""
        r = int(hex_color[0:2], 16)
        g = int(hex_color[2:4], 16)
        b = int(hex_color[4:6], 16)
        return ColorConverter._rgb_to_xy(r, g, b)
    
    @staticmethod
    def _rgb_to_xy(r: int, g: int, b: int) -> Dict[str, Any]:
        """
        Convert RGB values to CIE xy coordinates.
        Uses Philips Hue's color gamut B algorithm.
        """
        # Normalize RGB values
        r = r / 255.0
        g = g / 255.0
        b = b / 255.0
        
        # Apply gamma correction
        r = pow((r + 0.055) / 1.055, 2.4) if r > 0.04045 else r / 12.92
        g = pow((g + 0.055) / 1.055, 2.4) if g > 0.04045 else g / 12.92
        b = pow((b + 0.055) / 1.055, 2.4) if b > 0.04045 else b / 12.92
        
        # Convert to XYZ using sRGB matrix
        X = r * 0.664511 + g * 0.154324 + b * 0.162028
        Y = r * 0.283881 + g * 0.668433 + b * 0.047685
        Z = r * 0.000088 + g * 0.072310 + b * 0.986039
        
        # Convert to xy
        total = X + Y + Z
        if total == 0:
            return {"xy": [0.3227, 0.3290], "bri": 254}
        
        x = X / total
        y = Y / total
        
        # Calculate brightness (0-254 scale)
        brightness = int(Y * 254)
        brightness = max(1, min(254, brightness))
        
        return {"xy": [round(x, 4), round(y, 4)], "bri": brightness}
    
    @staticmethod
    def _kelvin_to_mired(kelvin: int) -> Dict[str, Any]:
        """Convert Kelvin color temperature to mired value."""
        # Clamp Kelvin to Hue's supported range (2000K - 6500K)
        kelvin = max(2000, min(6500, kelvin))
        
        # Convert to mired (micro reciprocal degree)
        mired = int(1000000 / kelvin)
        
        # Clamp to Hue's mired range (153-500)
        mired = max(153, min(500, mired))
        
        return {"ct": mired, "bri": 254}
    
    @staticmethod
    def get_available_colors() -> Dict[str, List[str]]:
        """Get lists of available color names by category."""
        return {
            "basic_colors": ["red", "green", "blue", "yellow", "orange", "purple", "pink", "cyan", "white"],
            "scene_colors": ["sunset", "sunrise", "ocean", "forest", "fire", "lavender"],
            "temperature_presets": ["warm_white", "soft_white", "neutral_white", "cool_white", "daylight", "candle"],
            "extended_colors": ["amber", "turquoise", "coral", "lime", "indigo", "teal", "gold", "silver"],
            "mood_aliases": ["relax", "concentrate", "energize", "sleep", "reading", "evening", "morning"],
            "formats": ["#RRGGBB hex codes", "rgb(r,g,b)", "temperature in Kelvin (e.g., 2700K)"]
        }
    
    @staticmethod
    def suggest_similar_colors(input_color: str) -> List[str]:
        """Suggest similar color names based on partial input."""
        input_lower = input_color.lower().strip()
        suggestions = []
        
        # Check all color names and aliases
        all_colors = list(COLOR_DEFINITIONS.keys()) + list(COLOR_ALIASES.keys())
        
        for color in all_colors:
            if input_lower in color or color.startswith(input_lower):
                suggestions.append(color)
        
        # Limit to 10 suggestions
        return suggestions[:10] if suggestions else ["Try: red, blue, warm_white, sunset, #FF5500"]