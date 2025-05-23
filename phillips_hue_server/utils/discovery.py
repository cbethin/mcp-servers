"""
Bridge discovery utilities for Philips Hue.
Handles automatic bridge discovery and setup.
"""

import json
import logging
import requests
import socket
from typing import Dict, Any, List, Optional
import time
import urllib3

# Suppress SSL warnings for self-signed certificates
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logger = logging.getLogger("discovery")

# Philips Hue discovery endpoints
DISCOVERY_MEETHUE_URL = "https://discovery.meethue.com/"
# Updated endpoint - the old one returns 404
DISCOVERY_NUPNP_URL = "https://discovery.meethue.com/"

# Application name for API key generation
APP_NAME = "phillips_hue_mcp_server"
DEVICE_NAME = "mcp_server"


class BridgeDiscovery:
    """Discover and setup Philips Hue bridges."""
    
    @staticmethod
    def discover_bridges() -> List[Dict[str, Any]]:
        """
        Discover Hue bridges on the network using multiple methods.
        Returns list of discovered bridges with IP addresses.
        """
        discovered_bridges = []
        logger.info("=== Starting Hue Bridge Discovery ===")
        
        # Method 1: Philips cloud discovery (recommended)
        try:
            logger.info("Method 1: Trying Philips cloud discovery at discovery.meethue.com")
            response = requests.get(DISCOVERY_MEETHUE_URL, timeout=10)
            logger.debug(f"Discovery API response status: {response.status_code}")
            
            if response.status_code == 200:
                bridges = response.json()
                logger.debug(f"Discovery API response: {bridges}")
                
                for bridge in bridges:
                    # Handle both old and new API response formats
                    ip = bridge.get("internalipaddress") or bridge.get("ip")
                    bridge_id = bridge.get("id", "unknown")
                    
                    if ip:
                        discovered_bridges.append({
                            "id": bridge_id,
                            "ip": ip,
                            "port": bridge.get("port", 80),
                            "name": f"Hue Bridge ({bridge_id[:6] if bridge_id != 'unknown' else 'Cloud'})",
                            "discovery_method": "cloud"
                        })
                        logger.info(f"✓ Found bridge via cloud: {ip} (ID: {bridge_id[:6]})")
                
                if not discovered_bridges:
                    logger.warning("Cloud discovery returned empty bridge list")
            else:
                logger.warning(f"Cloud discovery returned status {response.status_code}")
                
        except requests.exceptions.Timeout:
            logger.error("Cloud discovery timed out after 10 seconds")
        except Exception as e:
            logger.error(f"Cloud discovery failed: {type(e).__name__}: {e}")
        
        # Method 2: mDNS discovery (local network)
        if not discovered_bridges:
            try:
                logger.info("Method 2: Trying mDNS discovery on local network")
                mdns_bridges = BridgeDiscovery._discover_mdns()
                logger.debug(f"mDNS found {len(mdns_bridges)} potential bridges")
                
                for bridge in mdns_bridges:
                    # Check if not already discovered
                    if not any(b["ip"] == bridge["ip"] for b in discovered_bridges):
                        discovered_bridges.append(bridge)
                        logger.info(f"✓ Found bridge via mDNS: {bridge['ip']}")
                        
                if not mdns_bridges:
                    logger.debug("No bridges found via mDNS")
                    
            except Exception as e:
                logger.error(f"mDNS discovery failed: {type(e).__name__}: {e}")
        
        # Method 3: Manual IP scan (fallback)
        if not discovered_bridges:
            logger.info("Method 3: Trying manual IP scan on local subnet")
            try:
                local_bridges = BridgeDiscovery._scan_local_network()
                logger.debug(f"Network scan found {len(local_bridges)} bridges")
                
                for bridge in local_bridges:
                    discovered_bridges.append(bridge)
                    logger.info(f"✓ Found bridge via network scan: {bridge['ip']}")
                    
                if not local_bridges:
                    logger.info("No bridges found via network scan")
                    
            except Exception as e:
                logger.error(f"Local network scan failed: {type(e).__name__}: {e}")
        
        # Summary
        logger.info(f"=== Discovery Complete: Found {len(discovered_bridges)} bridge(s) ===")
        for i, bridge in enumerate(discovered_bridges):
            logger.info(f"  {i+1}. {bridge['name']} at {bridge['ip']} (via {bridge['discovery_method']})")
            
        return discovered_bridges
    
    @staticmethod
    def _discover_mdns() -> List[Dict[str, Any]]:
        """Discover bridges using mDNS (requires zeroconf)."""
        bridges = []
        
        # This is a simplified version - full mDNS would require zeroconf library
        # For now, we'll check the standard Hue bridge port
        try:
            # Get local IP to determine subnet
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            local_ip = s.getsockname()[0]
            s.close()
            
            # Check common Hue bridge hostnames
            hostnames = [
                "philips-hue", "philips-hue.local", "Philips-hue.local",
                "hue-bridge", "hue-bridge.local", "hue.local"
            ]
            
            for hostname in hostnames:
                try:
                    logger.debug(f"Trying hostname: {hostname}")
                    ip = socket.gethostbyname(hostname)
                    logger.debug(f"Resolved {hostname} to {ip}")
                    
                    if BridgeDiscovery._is_hue_bridge(ip):
                        bridges.append({
                            "ip": ip,
                            "name": f"Hue Bridge ({hostname})",
                            "discovery_method": "mdns"
                        })
                        logger.info(f"✓ Found bridge via hostname {hostname} at {ip}")
                        break  # Stop after first successful discovery
                        
                except socket.gaierror:
                    logger.debug(f"Could not resolve hostname: {hostname}")
                except Exception as e:
                    logger.debug(f"Error checking {hostname}: {e}")
        except Exception as e:
            logger.debug(f"mDNS discovery error: {e}")
        
        return bridges
    
    @staticmethod
    def _scan_local_network() -> List[Dict[str, Any]]:
        """Scan local network for Hue bridges."""
        bridges = []
        
        try:
            # Get local IP to determine subnet
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            local_ip = s.getsockname()[0]
            s.close()
            
            # Extract subnet (assuming /24)
            subnet = '.'.join(local_ip.split('.')[:-1])
            
            # Scan common IP ranges (extended list for better coverage)
            # Common router-assigned IPs and Hue bridge defaults
            scan_ranges = [
                range(1, 5),      # Router and early assignments
                range(50, 55),    # Common DHCP range start
                range(100, 110),  # Common static IP range
                range(200, 205),  # High DHCP range
                [254]             # Last usable IP
            ]
            
            ips_to_scan = []
            for r in scan_ranges:
                if isinstance(r, range):
                    ips_to_scan.extend(list(r))
                else:
                    ips_to_scan.extend(r)
            
            logger.info(f"Scanning {len(ips_to_scan)} IPs on subnet {subnet}")
            
            for i in ips_to_scan:
                ip = f"{subnet}.{i}"
                if BridgeDiscovery._is_hue_bridge(ip):
                    bridges.append({
                        "ip": ip,
                        "name": f"Hue Bridge ({ip})",
                        "discovery_method": "scan"
                    })
                    logger.info(f"Found Hue bridge at {ip}")
        except Exception as e:
            logger.debug(f"Network scan error: {e}")
        
        return bridges
    
    @staticmethod
    def _is_hue_bridge(ip: str) -> bool:
        """Check if an IP address hosts a Hue bridge."""
        logger.debug(f"Checking if {ip} is a Hue bridge...")
        
        # Try both HTTP and HTTPS since API v2 uses HTTPS
        protocols = [("http", 80), ("https", 443)]
        
        for protocol, default_port in protocols:
            try:
                url = f"{protocol}://{ip}/api/config"
                logger.debug(f"Trying {url}")
                
                # Disable SSL verification for self-signed certificates
                response = requests.get(url, timeout=3, verify=False)
                
                if response.status_code == 200:
                    data = response.json()
                    logger.debug(f"Got response from {ip}: {list(data.keys())[:5]}...")
                    
                    if "bridgeid" in data or "name" in data:
                        logger.info(f"✓ Confirmed Hue bridge at {ip} using {protocol.upper()}")
                        return True
                        
            except requests.exceptions.SSLError:
                logger.debug(f"SSL error on {ip} - likely self-signed cert")
            except requests.exceptions.ConnectTimeout:
                logger.debug(f"Connection timeout on {ip}")
            except requests.exceptions.ConnectionError:
                logger.debug(f"Connection refused on {ip}")
            except Exception as e:
                logger.debug(f"Error checking {ip}: {type(e).__name__}")
                
        return False
    
    @staticmethod
    def create_api_key(bridge_ip: str, app_name: str = APP_NAME) -> Dict[str, Any]:
        """
        Create an API key for the bridge.
        User must press the bridge button before calling this.
        """
        logger.info(f"Creating API key for bridge at {bridge_ip}")
        
        url = f"http://{bridge_ip}/api"
        body = {
            "devicetype": f"{app_name}#{DEVICE_NAME}"
        }
        
        try:
            response = requests.post(url, json=body, timeout=10)
            result = response.json()
            
            if isinstance(result, list) and len(result) > 0:
                if "success" in result[0]:
                    username = result[0]["success"]["username"]
                    logger.info("API key created successfully")
                    return {"success": True, "api_key": username}
                elif "error" in result[0]:
                    error = result[0]["error"]
                    error_desc = error.get("description", "Unknown error")
                    
                    if error.get("type") == 101:
                        return {
                            "success": False,
                            "error": "Link button not pressed. Please press the button on your Hue bridge and try again.",
                            "error_code": 101
                        }
                    else:
                        return {
                            "success": False,
                            "error": error_desc,
                            "error_code": error.get("type")
                        }
            
            return {"success": False, "error": "Unexpected response format"}
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Error creating API key: {e}")
            return {"success": False, "error": str(e)}
    
    @staticmethod
    def validate_bridge(bridge_ip: str, api_key: str) -> Dict[str, Any]:
        """Validate that a bridge IP and API key work correctly."""
        try:
            url = f"http://{bridge_ip}/api/{api_key}"
            response = requests.get(url, timeout=5)
            
            if response.status_code == 200:
                data = response.json()
                
                # Check if response is an error
                if isinstance(data, list) and len(data) > 0 and "error" in data[0]:
                    return {
                        "success": False,
                        "error": data[0]["error"].get("description", "Invalid API key")
                    }
                
                # Valid response should have bridge info
                if "config" in data or "lights" in data:
                    bridge_name = data.get("config", {}).get("name", "Unknown Bridge")
                    return {
                        "success": True,
                        "bridge_name": bridge_name,
                        "bridge_id": data.get("config", {}).get("bridgeid", "unknown")
                    }
            
            return {"success": False, "error": "Invalid response from bridge"}
            
        except requests.exceptions.RequestException as e:
            return {"success": False, "error": f"Connection failed: {str(e)}"}
    
    @staticmethod
    def get_bridge_info(bridge_ip: str) -> Dict[str, Any]:
        """Get basic information about a bridge without authentication."""
        try:
            url = f"http://{bridge_ip}/api/config"
            response = requests.get(url, timeout=5)
            
            if response.status_code == 200:
                config = response.json()
                return {
                    "success": True,
                    "info": {
                        "name": config.get("name", "Unknown"),
                        "bridge_id": config.get("bridgeid", "Unknown"),
                        "api_version": config.get("apiversion", "Unknown"),
                        "sw_version": config.get("swversion", "Unknown"),
                        "model_id": config.get("modelid", "Unknown"),
                        "ip": bridge_ip
                    }
                }
            
            return {"success": False, "error": "Could not retrieve bridge info"}
            
        except requests.exceptions.RequestException as e:
            return {"success": False, "error": str(e)}
    
    @staticmethod
    def wait_for_button_press(bridge_ip: str, timeout: int = 30) -> Dict[str, Any]:
        """
        Wait for user to press the bridge button and create API key.
        Polls every 2 seconds for the specified timeout.
        """
        logger.info(f"Waiting for button press on bridge at {bridge_ip}")
        
        start_time = time.time()
        while time.time() - start_time < timeout:
            result = BridgeDiscovery.create_api_key(bridge_ip)
            
            if result["success"]:
                return result
            
            # Only continue waiting if it's the button not pressed error
            if result.get("error_code") != 101:
                return result
            
            time.sleep(2)
        
        return {
            "success": False,
            "error": f"Timeout waiting for button press ({timeout} seconds)"
        }