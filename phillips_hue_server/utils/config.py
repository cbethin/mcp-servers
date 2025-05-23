"""
Configuration management for Philips Hue MCP server.
Handles bridge storage, API keys, and user preferences.
"""

import json
import logging
import os
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime

logger = logging.getLogger("config")

# Configuration file location
CONFIG_DIR = Path.home() / ".config" / "phillips_hue_mcp"
CONFIG_FILE = CONFIG_DIR / "config.json"

# Default configuration
DEFAULT_CONFIG = {
    "version": "2.0",
    "bridges": [],
    "preferences": {
        "default_transition_time": 4,  # 400ms
        "color_temperature_range": [153, 500],  # Mired range
        "brightness_range": [1, 254],
        "preferred_color_mode": "natural"  # "natural" or "technical"
    }
}


class HueConfig:
    """Manage Philips Hue MCP server configuration."""
    
    def __init__(self):
        self.config_file = CONFIG_FILE
        self.config = self.load_config()
    
    def load_config(self) -> Dict[str, Any]:
        """Load configuration from file or create default."""
        if not self.config_file.exists():
            logger.info("No configuration found, creating default config")
            return self._create_default_config()
        
        try:
            with open(self.config_file, 'r') as f:
                config = json.load(f)
                
            # Migrate old config format if needed
            if "HUE_BRIDGE_IP" in config:
                logger.info("Migrating old configuration format")
                config = self._migrate_v1_config(config)
                self.save_config(config)
            
            return config
        except Exception as e:
            logger.error(f"Error loading config: {e}")
            return self._create_default_config()
    
    def _create_default_config(self) -> Dict[str, Any]:
        """Create default configuration file."""
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        config = DEFAULT_CONFIG.copy()
        
        # Check for environment variables (backward compatibility)
        bridge_ip = os.environ.get('HUE_BRIDGE_IP')
        api_key = os.environ.get('HUE_API_KEY')
        
        if bridge_ip and api_key:
            logger.info("Found environment variables, importing to config")
            config["bridges"].append({
                "id": "primary",
                "name": "Primary Bridge",
                "ip": bridge_ip,
                "api_key": api_key,
                "api_version": "v1",
                "created_at": datetime.now().isoformat()
            })
        
        self.save_config(config)
        return config
    
    def _migrate_v1_config(self, old_config: Dict[str, Any]) -> Dict[str, Any]:
        """Migrate from v1 config format to v2."""
        new_config = DEFAULT_CONFIG.copy()
        
        if "HUE_BRIDGE_IP" in old_config and "HUE_API_KEY" in old_config:
            new_config["bridges"].append({
                "id": "primary",
                "name": "Primary Bridge (Migrated)",
                "ip": old_config["HUE_BRIDGE_IP"],
                "api_key": old_config["HUE_API_KEY"],
                "api_version": "v1",
                "created_at": datetime.now().isoformat()
            })
        
        return new_config
    
    def save_config(self, config: Optional[Dict[str, Any]] = None) -> None:
        """Save configuration to file."""
        if config is not None:
            self.config = config
        
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        
        try:
            with open(self.config_file, 'w') as f:
                json.dump(self.config, f, indent=2)
            logger.info("Configuration saved successfully")
        except Exception as e:
            logger.error(f"Error saving config: {e}")
    
    def add_bridge(self, bridge_ip: str, api_key: str, name: Optional[str] = None) -> str:
        """Add a new bridge to configuration."""
        bridge_id = f"bridge_{len(self.config['bridges']) + 1}"
        
        bridge = {
            "id": bridge_id,
            "name": name or f"Bridge {bridge_id}",
            "ip": bridge_ip,
            "api_key": api_key,
            "api_version": "v1",
            "created_at": datetime.now().isoformat()
        }
        
        self.config["bridges"].append(bridge)
        self.save_config()
        
        logger.info(f"Added bridge '{bridge['name']}' at {bridge_ip}")
        return bridge_id
    
    def remove_bridge(self, bridge_id: str) -> bool:
        """Remove a bridge from configuration."""
        original_count = len(self.config["bridges"])
        self.config["bridges"] = [b for b in self.config["bridges"] if b["id"] != bridge_id]
        
        if len(self.config["bridges"]) < original_count:
            self.save_config()
            logger.info(f"Removed bridge {bridge_id}")
            return True
        
        return False
    
    def get_bridge(self, bridge_id: str) -> Optional[Dict[str, Any]]:
        """Get specific bridge configuration."""
        for bridge in self.config["bridges"]:
            if bridge["id"] == bridge_id:
                return bridge
        return None
    
    def get_primary_bridge(self) -> Optional[Dict[str, Any]]:
        """Get the primary (first) bridge configuration."""
        if self.config["bridges"]:
            return self.config["bridges"][0]
        return None
    
    def set_primary_bridge(self, bridge_id: str) -> bool:
        """Set a bridge as primary by moving it to the first position."""
        bridge = None
        other_bridges = []
        
        for b in self.config["bridges"]:
            if b["id"] == bridge_id:
                bridge = b
            else:
                other_bridges.append(b)
        
        if bridge:
            self.config["bridges"] = [bridge] + other_bridges
            self.save_config()
            logger.info(f"Set bridge {bridge_id} as primary")
            return True
        
        return False
    
    def update_preferences(self, preferences: Dict[str, Any]) -> None:
        """Update user preferences."""
        self.config["preferences"].update(preferences)
        self.save_config()
        logger.info(f"Updated preferences: {preferences}")
    
    def get_preference(self, key: str, default: Any = None) -> Any:
        """Get a specific preference value."""
        return self.config["preferences"].get(key, default)


# Global configuration instance
hue_config = HueConfig()