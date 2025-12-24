"""Minecraft stats JSON parser and aggregation module."""

import json
from pathlib import Path
from typing import Any, Optional


def parse_player_stats(filepath: Path) -> dict[str, Any]:
    """Parse a player's stats JSON file.
    
    Args:
        filepath: Path to the player's stats JSON file.
        
    Returns:
        Parsed stats dictionary.
        
    Raises:
        FileNotFoundError: If file doesn't exist.
        json.JSONDecodeError: If file contains invalid JSON.
    """
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)


def get_stat_value(stats: dict, *keys: str, default: Any = 0) -> Any:
    """Safely get a nested value from stats dictionary.
    
    Args:
        stats: The stats dictionary.
        *keys: Sequence of keys to traverse.
        default: Default value if key not found.
        
    Returns:
        The value at the nested key path, or default.
    """
    current = stats
    for key in keys:
        if isinstance(current, dict) and key in current:
            current = current[key]
        else:
            return default
    return current


def calculate_playtime_hours(stats: dict) -> float:
    """Convert playtime from ticks to hours.
    
    Minecraft runs at 20 ticks/second.
    1 hour = 20 * 60 * 60 = 72000 ticks
    
    Args:
        stats: Player stats dictionary.
        
    Returns:
        Playtime in hours (rounded to 2 decimals).
    """
    ticks = get_stat_value(stats, "stats", "minecraft:custom", "minecraft:play_time")
    return round(ticks / 72000, 2)


def calculate_distance_km(stats: dict) -> float:
    """Calculate total distance traveled in kilometers.
    
    Sums all distance stats (stored in centimeters) and converts to km.
    
    Args:
        stats: Player stats dictionary.
        
    Returns:
        Total distance in kilometers (rounded to 2 decimals).
    """
    custom = get_stat_value(stats, "stats", "minecraft:custom", default={})
    
    distance_keys = [
        "minecraft:walk_one_cm",
        "minecraft:sprint_one_cm",
        "minecraft:swim_one_cm",
        "minecraft:boat_one_cm",
        "minecraft:horse_one_cm",
        "minecraft:fly_one_cm",
        "minecraft:climb_one_cm",
        "minecraft:crouch_one_cm",
        "minecraft:fall_one_cm",
        "minecraft:walk_on_water_one_cm",
        "minecraft:walk_under_water_one_cm",
    ]
    
    total_cm = sum(custom.get(key, 0) for key in distance_keys)
    return round(total_cm / 100000, 2)  # cm to km


def get_total_count(stats: dict, category: str) -> int:
    """Get total count for a category (mined, killed, crafted, etc).
    
    Args:
        stats: Player stats dictionary.
        category: Category key (e.g., "minecraft:mined").
        
    Returns:
        Sum of all items in the category.
    """
    category_dict = get_stat_value(stats, "stats", category, default={})
    return sum(category_dict.values()) if category_dict else 0


def get_top_item(stats: dict, category: str) -> tuple[Optional[str], int]:
    """Get the most frequent item in a category.
    
    Args:
        stats: Player stats dictionary.
        category: Category key (e.g., "minecraft:mined").
        
    Returns:
        Tuple of (item_name, count) or (None, 0) if empty.
    """
    category_dict = get_stat_value(stats, "stats", category, default={})
    
    if not category_dict:
        return None, 0
    
    top_item = max(category_dict.items(), key=lambda x: x[1])
    # Remove "minecraft:" prefix for cleaner display
    item_name = top_item[0].replace("minecraft:", "")
    return item_name, top_item[1]


def get_deaths(stats: dict) -> int:
    """Get player death count.
    
    Args:
        stats: Player stats dictionary.
        
    Returns:
        Number of deaths.
    """
    return get_stat_value(stats, "stats", "minecraft:custom", "minecraft:deaths")


def get_mob_kills(stats: dict) -> int:
    """Get total mob kills.
    
    Args:
        stats: Player stats dictionary.
        
    Returns:
        Total number of mobs killed.
    """
    return get_stat_value(stats, "stats", "minecraft:custom", "minecraft:mob_kills")


def get_tools_broken(stats: dict) -> int:
    """Get total tools broken.
    
    Args:
        stats: Player stats dictionary.
        
    Returns:
        Total number of tools broken.
    """
    return get_total_count(stats, "minecraft:broken")


def extract_weekly_summary(stats: dict) -> dict[str, Any]:
    """Extract complete weekly summary from player stats.
    
    Args:
        stats: Player stats dictionary.
        
    Returns:
        Dictionary containing all weekly stats and top items.
    """
    # Main stats
    summary = {
        "playtime_hours": calculate_playtime_hours(stats),
        "distance_km": calculate_distance_km(stats),
        "mob_kills": get_mob_kills(stats),
        "blocks_mined": get_total_count(stats, "minecraft:mined"),
        "blocks_crafted": get_total_count(stats, "minecraft:crafted"),
        "deaths": get_deaths(stats),
        "tools_broken": get_tools_broken(stats),
    }
    
    # Top items per category
    top_mined = get_top_item(stats, "minecraft:mined")
    top_killed = get_top_item(stats, "minecraft:killed")
    top_broken = get_top_item(stats, "minecraft:broken")
    top_crafted = get_top_item(stats, "minecraft:crafted")
    
    summary["top_items"] = {
        "mined": {"name": top_mined[0], "count": top_mined[1]},
        "killed": {"name": top_killed[0], "count": top_killed[1]},
        "broken": {"name": top_broken[0], "count": top_broken[1]},
        "crafted": {"name": top_crafted[0], "count": top_crafted[1]},
    }
    
    return summary


def get_player_uuid_from_filename(filepath: Path) -> str:
    """Extract player UUID from stats filename.
    
    Args:
        filepath: Path to stats file (e.g., uuid.json).
        
    Returns:
        Player UUID (filename without extension).
    """
    return filepath.stem


def load_usercache(usercache_path: Path) -> dict[str, str]:
    """Load the usercache.json and return a UUID->name mapping.
    
    Args:
        usercache_path: Path to usercache.json file.
        
    Returns:
        Dictionary mapping UUID to player name.
    """
    if not usercache_path.exists():
        return {}
    
    try:
        with open(usercache_path, "r", encoding="utf-8") as f:
            cache = json.load(f)
        return {entry["uuid"]: entry["name"] for entry in cache}
    except (json.JSONDecodeError, KeyError, TypeError):
        return {}


def get_player_name(uuid: str, usercache: dict[str, str]) -> Optional[str]:
    """Get player name from usercache by UUID.
    
    Args:
        uuid: Player UUID.
        usercache: Dictionary from load_usercache().
        
    Returns:
        Player name or None if not found.
    """
    return usercache.get(uuid)

