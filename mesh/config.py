"""
Configuration handling for MeshChat application
"""
import json
from pathlib import Path


def get_config_path():
    """Get the configuration file path"""
    home_dir = Path.home()
    config_dir = home_dir / ".config" / "meshcore"
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir / "mesh-cli.json"


def load_config():
    """Load configuration from file"""
    config_path = get_config_path()
    if config_path.exists():
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
    return {}


def save_config(config):
    """Save configuration to file"""
    config_path = get_config_path()
    try:
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2)
    except IOError as e:
        print(f"Error saving configuration: {e}")


def get_connection_params():
    """Get connection parameters from config or user input"""
    from .constants import ANSI_BCYAN, ANSI_GREEN, ANSI_BRED, ANSI_BGREEN, ANSI_END
    config = load_config()

    # Check if config has required parameters
    if 'host' in config and 'port' in config:
        host = config['host']
        port = config['port']
        print(f"{ANSI_BCYAN}Using saved configuration: {host}:{port}{ANSI_END}")
    else:
        print(f"{ANSI_BCYAN}Please enter connection parameters:{ANSI_END}")
        host = input(f"{ANSI_GREEN}Host (default: 127.0.0.1): {ANSI_END}") or "127.0.0.1"
        port_input = input(f"{ANSI_GREEN}Port (default: 5000): {ANSI_END}") or "5000"
        try:
            port = int(port_input)
        except ValueError:
            port = 5000
            print(f"{ANSI_BRED}Invalid port number, using default: 5000{ANSI_END}")

        # Save configuration
        config['host'] = host
        config['port'] = port
        save_config(config)
        print(f"{ANSI_BGREEN}Configuration saved to {get_config_path()}{ANSI_END}")

    return host, port
