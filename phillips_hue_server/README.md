# Phillips Hue MCP Server

A Model Context Protocol (MCP) server for controlling Philips Hue smart lighting systems through LLMs like Claude. This server provides comprehensive control over your Hue lights with natural language color support and advanced features.

## Features

- **Auto-discovery**: Automatically finds Hue bridges on your network
- **Natural language colors**: Use descriptions like "sunset", "warm white", "ocean blue"
- **Scene management**: Apply, save, and manage lighting scenes
- **Smooth transitions**: Create beautiful lighting transitions over time
- **Group control**: Control multiple lights as groups
- **Comprehensive status**: Get detailed information about your lighting system

## Getting Started

### Prerequisites

- Python 3.10+
- Philips Hue Bridge on your local network
- [`uv`](https://github.com/astral-sh/uv) package manager

### Installation

1. Install uv if you haven't already:
   ```sh
   pip install uv
   ```

2. Create and activate virtual environment:
   ```sh
   uv venv
   source .venv/bin/activate
   ```

3. Install dependencies:
   ```sh
   uv sync
   ```

4. Run the dev server:
   ```sh
   mcp dev main.py
   ```

5. Install to Claude MCP configuration:
   ```sh
   mcp install main.py
   ```

### Initial Setup

When using the server for the first time:

1. Run the `setup()` tool - it will discover your bridge automatically
2. Press the button on your Hue bridge when prompted
3. The server will save your configuration for future use

```python
# In Claude or your MCP client:
setup()  # Follow the prompts
```

## Running with Docker

### Build the Docker image:
```sh
docker build -t phillips-hue-server .
```

### Run the server:
```sh
docker run -i --rm phillips-hue-server
```

### Run with local code mounted (for development):
```sh
docker run -i --rm --mount type=bind,src=$(pwd),dst=/app phillips-hue-server
```

## Claude Desktop Configuration

Add to your `claude_desktop_config.json`:

### Using local Python:
```json
{
  "phillips_hue": {
    "command": "mcp",
    "args": ["run", "main.py"],
    "cwd": "/path/to/phillips_hue_server"
  }
}
```

### Using Docker:
```json
{
  "phillips_hue": {
    "command": "docker",
    "args": [
      "run", "-i", "--rm",
      "--mount", "type=bind,src=/path/to/phillips_hue_server,dst=/app",
      "phillips-hue-server"
    ]
  }
}
```

## Available Tools

### 1. setup(bridge_ip: Optional[str])
Complete bridge discovery and setup workflow. Auto-discovers bridges if no IP provided.

```python
setup()  # Auto-discover
setup("192.168.1.100")  # Use specific IP
```

### 2. control(target, color, brightness, on)
Universal light/group control with natural language.

```python
control("all", on=False)  # Turn off all lights
control("Kitchen", color="warm white", brightness=200)
control("Living Room", color="sunset")
```

### 3. get_status(resource, id)
Get information about lights, groups, or bridges.

```python
get_status("lights")  # All lights
get_status("groups", "Living Room")  # Specific group
get_status("all")  # Everything
```

### 4. scene(name, target, transition_time)
Apply Hue or custom scenes.

```python
scene("Relax", "Living Room")
scene("sunset_mood")  # Custom saved scene
```

### 5. save_scene(name, notes)
Save current lighting state as a custom scene.

```python
save_scene("movie_night", "Dim ambient lighting for movies")
```

### 6. manage_scenes(action, scene_id)
List, delete, or get info about scenes.

```python
manage_scenes("list")
manage_scenes("delete", "old_scene")
manage_scenes("info", "Relax")
```

### 7. transition(target, to_color, duration, from_color)
Create smooth light transitions.

```python
transition("Living Room", "sunset", 10)
transition("all", "warm white", 30, from_color="daylight")
```

### 8. bridge(action)
Bridge management utilities.

```python
bridge("status")  # Quick status check
bridge("test")    # Test connection
bridge("config")  # Get bridge configuration
```

### 9. groups(action, name, lights)
Create or delete light groups.

```python
groups("create", "Bedroom", ["Lamp 1", "Lamp 2"])
groups("delete", "Bedroom")
```

### 10. config(action, settings)
Manage server configuration.

```python
config("show")
config("reset")
config("update", {"default_transition": 2})
```

### 11. colors(query)
Get available colors or suggestions.

```python
colors()  # List all available colors
colors("sunset")  # Get similar colors
```

### 12. test()
Test server functionality and connection.

```python
test()  # Run diagnostic tests
```

## Natural Language Colors

The server supports a wide variety of natural language color descriptions:

### Temperature Presets
- `candle` - Warm candlelight (2000K)
- `warm_white` - Cozy warm white (2700K)
- `soft_white` - Soft white (3000K)
- `daylight` - Bright daylight (5000K)
- `cool_white` - Cool white (6500K)
- `moonlight` - Cool moonlight (4100K)

### Nature Colors
- `sunset` - Orange/pink sunset hues
- `sunrise` - Soft morning colors
- `ocean` - Deep blue ocean tones
- `forest` - Natural green
- `autumn` - Warm fall colors
- `spring` - Fresh spring greens
- `summer` - Bright summer sky
- `winter` - Cool winter blue

### Mood Colors
- `relax` - Calming warm tones
- `energize` - Bright, energizing light
- `focus` - Neutral white for concentration
- `romance` - Soft pink/red ambiance
- `party` - Dynamic party colors
- `meditation` - Soft, calming hues
- `sleep` - Very warm, dim light
- `wake` - Gradually brightening light

### Basic Colors
Standard colors like `red`, `green`, `blue`, `yellow`, `purple`, `orange`, `pink`, `cyan`, `magenta`, `white`

### Hex Codes
You can also use hex color codes like `#FF5500` for precise control.

## Environment Variables

Optional environment variables:

```sh
export HUE_BRIDGE_IP="192.168.1.X"    # Skip discovery, use this IP
export HUE_API_KEY="your-api-key"     # Use existing API key
export DEBUG=1                        # Enable debug logging
```

## Troubleshooting

### Bridge not found
- Ensure you're on the same network as your Hue bridge
- Check that the bridge is powered on
- Try specifying the IP directly: `setup("192.168.1.X")`

### Connection refused
- The bridge might be at a different IP
- Run `setup()` again to rediscover
- Check your firewall settings

### Lights not responding
- Use `get_status("lights")` to check if lights are reachable
- Ensure lights are powered on
- Check if lights are assigned to correct groups

## Advanced Usage

### Creating Complex Scenes

```python
# Set up movie night scene
control("TV Backlight", color="ocean", brightness=50)
control("Ceiling", on=False)
control("Side Lamps", color="warm white", brightness=30)
save_scene("movie_night", "Perfect lighting for watching movies")
```

### Sunrise Simulation

```python
# Gradual sunrise over 30 minutes
transition("Bedroom", "sunrise", 1800, from_color="moonlight")
```

### Party Mode

```python
# Rapid color changes for parties
control("Living Room", color="party")
transition("all", "energize", 5)
```

## Project Structure

```
phillips_hue_server/
├── main.py              # Entry point
├── server.py            # MCP server with 12 tools
├── utils/
│   ├── hue_api.py      # Hue API interactions
│   ├── config.py       # Configuration management
│   ├── discovery.py    # Bridge discovery
│   ├── colors.py       # Color conversion utilities
│   └── validation.py   # Input validation
├── scenes/             # Saved custom scenes
├── requirements.txt    # Dependencies
├── pyproject.toml      # Project metadata
└── Dockerfile         # Docker configuration
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly with your Hue system
5. Submit a pull request

## License

MIT License

## Support

For issues or questions:
- Check the troubleshooting section above
- Review the tool documentation
- Submit an issue on GitHub