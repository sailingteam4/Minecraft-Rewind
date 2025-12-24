"""SQLite database module for storing weekly snapshots."""

import sqlite3
from datetime import date, datetime
from pathlib import Path
from typing import Any, Optional

from config import DB_PATH


def get_connection() -> sqlite3.Connection:
    """Get a database connection with row factory.
    
    Returns:
        SQLite connection configured with Row factory.
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Initialize the database schema.
    
    Creates all required tables if they don't exist.
    """
    conn = get_connection()
    cursor = conn.cursor()
    
    # Snapshots table - main record per player per extraction date
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            player_uuid TEXT NOT NULL,
            player_name TEXT,
            extraction_date DATE NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(player_uuid, extraction_date)
        )
    """)
    
    # Add player_name column if it doesn't exist (migration)
    try:
        cursor.execute("ALTER TABLE snapshots ADD COLUMN player_name TEXT")
    except sqlite3.OperationalError:
        pass  # Column already exists
    
    # Stats table - key-value pairs for flexibility
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS stats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            snapshot_id INTEGER NOT NULL,
            stat_key TEXT NOT NULL,
            stat_value REAL NOT NULL,
            FOREIGN KEY (snapshot_id) REFERENCES snapshots(id) ON DELETE CASCADE
        )
    """)
    
    # Top items table - best item per category
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS top_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            snapshot_id INTEGER NOT NULL,
            category TEXT NOT NULL,
            item_name TEXT,
            item_count INTEGER NOT NULL DEFAULT 0,
            FOREIGN KEY (snapshot_id) REFERENCES snapshots(id) ON DELETE CASCADE
        )
    """)
    
    # Indexes for performance
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_snapshots_player 
        ON snapshots(player_uuid)
    """)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_snapshots_date 
        ON snapshots(extraction_date)
    """)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_stats_snapshot 
        ON stats(snapshot_id)
    """)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_top_items_snapshot 
        ON top_items(snapshot_id)
    """)
    
    conn.commit()
    conn.close()


def save_snapshot(
    player_uuid: str,
    extraction_date: date,
    summary: dict[str, Any],
    player_name: Optional[str] = None
) -> int:
    """Save a weekly snapshot for a player.
    
    Args:
        player_uuid: Player's Minecraft UUID.
        extraction_date: Date of extraction.
        summary: Stats summary from extract_weekly_summary().
        player_name: Optional Minecraft username.
        
    Returns:
        The snapshot ID.
        
    Raises:
        sqlite3.IntegrityError: If snapshot already exists for this date.
    """
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        # Insert snapshot record
        cursor.execute("""
            INSERT INTO snapshots (player_uuid, player_name, extraction_date)
            VALUES (?, ?, ?)
        """, (player_uuid, player_name, extraction_date.isoformat()))
        
        snapshot_id = cursor.lastrowid
        
        # Insert main stats
        stat_keys = [
            "playtime_hours", "distance_km", "mob_kills",
            "blocks_mined", "blocks_crafted", "deaths", "tools_broken"
        ]
        
        for key in stat_keys:
            if key in summary:
                cursor.execute("""
                    INSERT INTO stats (snapshot_id, stat_key, stat_value)
                    VALUES (?, ?, ?)
                """, (snapshot_id, key, summary[key]))
        
        # Insert top items
        if "top_items" in summary:
            for category, item_data in summary["top_items"].items():
                cursor.execute("""
                    INSERT INTO top_items (snapshot_id, category, item_name, item_count)
                    VALUES (?, ?, ?, ?)
                """, (
                    snapshot_id,
                    category,
                    item_data.get("name"),
                    item_data.get("count", 0)
                ))
        
        conn.commit()
        return snapshot_id
        
    finally:
        conn.close()


def get_snapshot(player_uuid: str, extraction_date: date) -> Optional[dict]:
    """Get a specific snapshot for a player.
    
    Args:
        player_uuid: Player's Minecraft UUID.
        extraction_date: Date of extraction.
        
    Returns:
        Snapshot data dictionary or None if not found.
    """
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            SELECT id, player_uuid, player_name, extraction_date, created_at
            FROM snapshots
            WHERE player_uuid = ? AND extraction_date = ?
        """, (player_uuid, extraction_date.isoformat()))
        
        row = cursor.fetchone()
        if not row:
            return None
        
        snapshot = dict(row)
        snapshot_id = row["id"]
        
        # Get stats
        cursor.execute("""
            SELECT stat_key, stat_value FROM stats WHERE snapshot_id = ?
        """, (snapshot_id,))
        snapshot["stats"] = {row["stat_key"]: row["stat_value"] for row in cursor.fetchall()}
        
        # Get top items
        cursor.execute("""
            SELECT category, item_name, item_count FROM top_items WHERE snapshot_id = ?
        """, (snapshot_id,))
        snapshot["top_items"] = {
            row["category"]: {"name": row["item_name"], "count": row["item_count"]}
            for row in cursor.fetchall()
        }
        
        return snapshot
        
    finally:
        conn.close()


def get_latest_snapshots(player_uuid: str, limit: int = 10) -> list[dict]:
    """Get the latest snapshots for a player.
    
    Args:
        player_uuid: Player's Minecraft UUID.
        limit: Maximum number of snapshots to return.
        
    Returns:
        List of snapshot dictionaries, newest first.
    """
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            SELECT id, player_uuid, player_name, extraction_date, created_at
            FROM snapshots
            WHERE player_uuid = ?
            ORDER BY extraction_date DESC
            LIMIT ?
        """, (player_uuid, limit))
        
        snapshots = []
        for row in cursor.fetchall():
            snapshot = dict(row)
            snapshot_id = row["id"]
            
            # Get stats
            cursor.execute("""
                SELECT stat_key, stat_value FROM stats WHERE snapshot_id = ?
            """, (snapshot_id,))
            snapshot["stats"] = {r["stat_key"]: r["stat_value"] for r in cursor.fetchall()}
            
            # Get top items
            cursor.execute("""
                SELECT category, item_name, item_count FROM top_items WHERE snapshot_id = ?
            """, (snapshot_id,))
            snapshot["top_items"] = {
                r["category"]: {"name": r["item_name"], "count": r["item_count"]}
                for r in cursor.fetchall()
            }
            
            snapshots.append(snapshot)
        
        return snapshots
        
    finally:
        conn.close()


def get_all_players() -> list[dict[str, str]]:
    """Get list of all players in the database.
    
    Returns:
        List of dicts with player_uuid and player_name.
    """
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            SELECT player_uuid, player_name 
            FROM snapshots 
            GROUP BY player_uuid 
            ORDER BY MAX(extraction_date) DESC
        """)
        return [{"uuid": row["player_uuid"], "name": row["player_name"]} for row in cursor.fetchall()]
    finally:
        conn.close()


def compare_snapshots(
    player_uuid: str,
    date1: date,
    date2: date
) -> Optional[dict[str, Any]]:
    """Compare two snapshots and calculate the difference.
    
    Args:
        player_uuid: Player's Minecraft UUID.
        date1: Earlier date.
        date2: Later date.
        
    Returns:
        Dictionary with comparison data, or None if either snapshot missing.
    """
    snap1 = get_snapshot(player_uuid, date1)
    snap2 = get_snapshot(player_uuid, date2)
    
    if not snap1 or not snap2:
        return None
    
    comparison = {
        "player_uuid": player_uuid,
        "from_date": date1.isoformat(),
        "to_date": date2.isoformat(),
        "stats_diff": {},
        "stats_from": snap1["stats"],
        "stats_to": snap2["stats"],
        "top_items_from": snap1["top_items"],
        "top_items_to": snap2["top_items"],
    }
    
    # Calculate differences for each stat
    all_keys = set(snap1["stats"].keys()) | set(snap2["stats"].keys())
    for key in all_keys:
        val1 = snap1["stats"].get(key, 0)
        val2 = snap2["stats"].get(key, 0)
        diff = val2 - val1
        comparison["stats_diff"][key] = {
            "from": val1,
            "to": val2,
            "diff": round(diff, 2),
            "percent": round((diff / val1 * 100) if val1 != 0 else 0, 1)
        }
    
    return comparison


def delete_snapshot(player_uuid: str, extraction_date: date) -> bool:
    """Delete a snapshot and its related data.
    
    Args:
        player_uuid: Player's Minecraft UUID.
        extraction_date: Date of extraction.
        
    Returns:
        True if deleted, False if not found.
    """
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        # Enable foreign key cascade
        cursor.execute("PRAGMA foreign_keys = ON")
        
        cursor.execute("""
            DELETE FROM snapshots
            WHERE player_uuid = ? AND extraction_date = ?
        """, (player_uuid, extraction_date.isoformat()))
        
        deleted = cursor.rowcount > 0
        conn.commit()
        return deleted
        
    finally:
        conn.close()


# Initialize database on module import
init_db()
