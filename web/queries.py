"""Database queries for web interface."""

import sqlite3
from datetime import date
from typing import Any, Optional
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import DB_PATH


def get_connection() -> sqlite3.Connection:
    """Get a database connection with row factory."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def get_leaderboard(stat_key: str, limit: int = 5) -> list[dict]:
    """Get top players for a specific stat.
    
    Args:
        stat_key: The stat to rank by (e.g., 'blocks_mined', 'playtime_hours')
        limit: Number of top players to return
        
    Returns:
        List of player dicts with uuid, name, and stat value
    """
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        # Get the latest snapshot for each player with the requested stat
        cursor.execute("""
            SELECT 
                s.player_uuid,
                s.player_name,
                st.stat_value,
                s.extraction_date
            FROM snapshots s
            JOIN stats st ON st.snapshot_id = s.id
            WHERE st.stat_key = ?
            AND s.extraction_date = (
                SELECT MAX(s2.extraction_date) 
                FROM snapshots s2 
                WHERE s2.player_uuid = s.player_uuid
            )
            ORDER BY st.stat_value DESC
            LIMIT ?
        """, (stat_key, limit))
        
        results = []
        for rank, row in enumerate(cursor.fetchall(), 1):
            results.append({
                "rank": rank,
                "uuid": row["player_uuid"],
                "name": row["player_name"] or row["player_uuid"][:8],
                "value": row["stat_value"],
                "date": row["extraction_date"]
            })
        return results
        
    finally:
        conn.close()


def get_all_leaderboards() -> dict[str, list[dict]]:
    """Get all leaderboards for the global rewind page."""
    return {
        "blocks_mined": get_leaderboard("blocks_mined", 5),
        "playtime_hours": get_leaderboard("playtime_hours", 5),
        "mob_kills": get_leaderboard("mob_kills", 5),
        "deaths": get_leaderboard("deaths", 5),
        "tools_broken": get_leaderboard("tools_broken", 5),
        "distance_km": get_leaderboard("distance_km", 5),
        "blocks_crafted": get_leaderboard("blocks_crafted", 5),
    }


def get_global_stats() -> dict[str, Any]:
    """Get aggregated global statistics."""
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        # Get latest snapshot date
        cursor.execute("SELECT MAX(extraction_date) as latest FROM snapshots")
        latest_date = cursor.fetchone()["latest"]
        
        # Count total players
        cursor.execute("SELECT COUNT(DISTINCT player_uuid) as count FROM snapshots")
        total_players = cursor.fetchone()["count"]
        
        # Sum all stats from latest snapshots
        cursor.execute("""
            SELECT 
                st.stat_key,
                SUM(st.stat_value) as total
            FROM stats st
            JOIN snapshots s ON s.id = st.snapshot_id
            WHERE s.extraction_date = (
                SELECT MAX(s2.extraction_date) 
                FROM snapshots s2 
                WHERE s2.player_uuid = s.player_uuid
            )
            GROUP BY st.stat_key
        """)
        
        totals = {row["stat_key"]: row["total"] for row in cursor.fetchall()}
        
        return {
            "latest_date": latest_date,
            "total_players": total_players,
            "totals": totals
        }
        
    finally:
        conn.close()


def get_player_list() -> list[dict]:
    """Get list of all players for search/autocomplete."""
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            SELECT DISTINCT player_uuid, player_name
            FROM snapshots
            WHERE player_name IS NOT NULL
            ORDER BY player_name
        """)
        return [{"uuid": row["player_uuid"], "name": row["player_name"]} 
                for row in cursor.fetchall()]
    finally:
        conn.close()


def get_player_by_name(player_name: str) -> Optional[dict]:
    """Find player by name (case-insensitive)."""
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            SELECT DISTINCT player_uuid, player_name
            FROM snapshots
            WHERE LOWER(player_name) = LOWER(?)
        """, (player_name,))
        row = cursor.fetchone()
        if row:
            return {"uuid": row["player_uuid"], "name": row["player_name"]}
        return None
    finally:
        conn.close()


def get_player_stats(player_uuid: str) -> Optional[dict]:
    """Get full stats for a player from their latest snapshot."""
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        # Get latest snapshot
        cursor.execute("""
            SELECT id, player_uuid, player_name, extraction_date
            FROM snapshots
            WHERE player_uuid = ?
            ORDER BY extraction_date DESC
            LIMIT 1
        """, (player_uuid,))
        
        snapshot = cursor.fetchone()
        if not snapshot:
            return None
        
        result = {
            "uuid": snapshot["player_uuid"],
            "name": snapshot["player_name"] or snapshot["player_uuid"][:8],
            "extraction_date": snapshot["extraction_date"],
            "stats": {},
            "top_items": {}
        }
        
        # Get stats
        cursor.execute("""
            SELECT stat_key, stat_value 
            FROM stats 
            WHERE snapshot_id = ?
        """, (snapshot["id"],))
        result["stats"] = {row["stat_key"]: row["stat_value"] for row in cursor.fetchall()}
        
        # Get top items
        cursor.execute("""
            SELECT category, item_name, item_count
            FROM top_items
            WHERE snapshot_id = ?
        """, (snapshot["id"],))
        result["top_items"] = {
            row["category"]: {"name": row["item_name"], "count": row["item_count"]}
            for row in cursor.fetchall()
        }
        
        return result
        
    finally:
        conn.close()


def get_player_history(player_uuid: str, limit: int = 10) -> list[dict]:
    """Get player's stat history over time."""
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            SELECT s.id, s.extraction_date
            FROM snapshots s
            WHERE s.player_uuid = ?
            ORDER BY s.extraction_date DESC
            LIMIT ?
        """, (player_uuid, limit))
        
        history = []
        for snapshot in cursor.fetchall():
            cursor.execute("""
                SELECT stat_key, stat_value 
                FROM stats 
                WHERE snapshot_id = ?
            """, (snapshot["id"],))
            
            history.append({
                "date": snapshot["extraction_date"],
                "stats": {row["stat_key"]: row["stat_value"] for row in cursor.fetchall()}
            })
        
        return history
        
    finally:
        conn.close()


def get_player_ranks(player_uuid: str) -> dict[str, int]:
    """Get player's rank in each category."""
    stat_keys = ["blocks_mined", "playtime_hours", "mob_kills", "deaths", 
                 "tools_broken", "distance_km", "blocks_crafted"]
    ranks = {}
    
    for stat_key in stat_keys:
        leaderboard = get_leaderboard(stat_key, 100)
        for entry in leaderboard:
            if entry["uuid"] == player_uuid:
                ranks[stat_key] = entry["rank"]
                break
        else:
            ranks[stat_key] = 0  # Not ranked
    
    return ranks
