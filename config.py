"""
Configuration module for handling API keys and settings.
This works both in development and when bundled as .exe
"""

import os
import sys
from pathlib import Path


def get_base_path():
    """Get the base path for the application (works with PyInstaller)"""
    if getattr(sys, "frozen", False):
        # Running as compiled executable
        return Path(sys._MEIPASS)
    else:
        # Running as script
        return Path(__file__).parent


def get_env_file_path():
    """Get the path to the .env file"""
    base_path = get_base_path()
    return base_path / ".env"


def load_api_keys():
    """Load API keys from .env file or environment variables"""
    api_keys = {}

    # Try to load from .env file first
    env_path = get_env_file_path()
    if env_path.exists():
        with open(env_path, "r") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    api_keys[key.strip()] = value.strip()

    # Override with environment variables if they exist
    elevenlabs_key = os.getenv("ELEVENLABS_API_KEY")
    if elevenlabs_key:
        api_keys["ELEVENLABS_API_KEY"] = elevenlabs_key

    gemini_key = os.getenv("GOOGLE_API_KEY")
    if gemini_key:
        api_keys["GOOGLE_API_KEY"] = gemini_key

    return api_keys


# Load API keys once at import
API_KEYS = load_api_keys()


def get_api_key(key_name: str) -> str:
    """Get an API key by name"""
    return API_KEYS.get(key_name, "")


def get_asset_path(relative_path: str):
    """Get the full path to an asset file (works with PyInstaller)"""
    base_path = get_base_path()
    return str(base_path / relative_path)
