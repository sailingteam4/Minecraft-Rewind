"""Configuration for Minecraft Rewind system."""

import os
from pathlib import Path

# Base directory of the project
BASE_DIR = Path(__file__).parent.resolve()

# Minecraft server directory (PufferPanel)
SERVER_DIR = Path(os.getenv(
    "MINECRAFT_SERVER_DIR",
    "/var/lib/pufferpanel/servers/96c4c3ef"
))

# Stats directory
STATS_DIR = Path(os.getenv(
    "MINECRAFT_STATS_DIR",
    str(SERVER_DIR / "world" / "stats")
))

# Usercache for player name lookup
USERCACHE_PATH = SERVER_DIR / "usercache.json"

# Database configuration
DATA_DIR = BASE_DIR / "data"
DB_PATH = DATA_DIR / "rewind.db"

# Logging
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

# Ensure data directory exists
DATA_DIR.mkdir(exist_ok=True)

