#!/usr/bin/env python3
"""Minecraft Rewind - CLI entry point.

Usage:
    python -m src.rewind snapshot [--stats-dir PATH]
    python -m src.rewind compare --player UUID [--weeks N]
    python -m src.rewind export --player UUID [--format json|csv]
    python -m src.rewind list
"""

import argparse
import csv
import json
import logging
import sys
from datetime import date, timedelta
from pathlib import Path
from typing import Optional

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import STATS_DIR, LOG_LEVEL, USERCACHE_PATH
from src.stats_parser import (
    parse_player_stats,
    extract_weekly_summary,
    get_player_uuid_from_filename,
    load_usercache,
    get_player_name,
)
from src.database import (
    save_snapshot,
    get_latest_snapshots,
    get_all_players,
    compare_snapshots,
    get_snapshot,
)

# Configure logging
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL),
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def cmd_snapshot(args: argparse.Namespace) -> int:
    """Execute the snapshot command.
    
    Reads all player stats files and creates weekly snapshots.
    """
    stats_dir = Path(args.stats_dir) if args.stats_dir else STATS_DIR
    extraction_date = date.today()
    
    if args.date:
        try:
            extraction_date = date.fromisoformat(args.date)
        except ValueError:
            logger.error(f"Invalid date format: {args.date}. Use YYYY-MM-DD.")
            return 1
    
    logger.info(f"Creating snapshots for {extraction_date} from {stats_dir}")
    
    if not stats_dir.exists():
        logger.error(f"Stats directory not found: {stats_dir}")
        return 1
    
    # Find all JSON files
    json_files = list(stats_dir.glob("*.json"))
    
    if not json_files:
        logger.warning(f"No stats files found in {stats_dir}")
        return 0
    
    # Load usercache for player names
    usercache = load_usercache(USERCACHE_PATH)
    if usercache:
        logger.info(f"Loaded {len(usercache)} players from usercache")
    
    success_count = 0
    error_count = 0
    
    for filepath in json_files:
        player_uuid = get_player_uuid_from_filename(filepath)
        player_name = get_player_name(player_uuid, usercache)
        
        try:
            if args.dry_run:
                logger.info(f"[DRY RUN] Would process: {player_uuid}")
                stats = parse_player_stats(filepath)
                summary = extract_weekly_summary(stats)
                logger.info(f"  Stats: {json.dumps(summary, indent=2)}")
                success_count += 1
                continue
            
            stats = parse_player_stats(filepath)
            summary = extract_weekly_summary(stats)
            
            snapshot_id = save_snapshot(player_uuid, extraction_date, summary, player_name)
            display_name = f"{player_name} ({player_uuid})" if player_name else player_uuid
            logger.info(f"Saved snapshot {snapshot_id} for player {display_name}")
            success_count += 1
            
        except Exception as e:
            logger.error(f"Error processing {player_uuid}: {e}")
            error_count += 1
    
    logger.info(f"Completed: {success_count} succeeded, {error_count} failed")
    return 0 if error_count == 0 else 1


def cmd_compare(args: argparse.Namespace) -> int:
    """Execute the compare command.
    
    Compares the last N weeks of snapshots for a player.
    """
    player_uuid = args.player
    weeks = args.weeks or 2
    
    # Get latest snapshots
    snapshots = get_latest_snapshots(player_uuid, limit=weeks)
    
    if len(snapshots) < 2:
        logger.warning(f"Not enough snapshots for comparison. Found: {len(snapshots)}")
        return 1
    
    # Compare the two most recent
    date1 = date.fromisoformat(snapshots[1]["extraction_date"])
    date2 = date.fromisoformat(snapshots[0]["extraction_date"])
    
    comparison = compare_snapshots(player_uuid, date1, date2)
    
    if not comparison:
        logger.error("Could not compare snapshots")
        return 1
    
    print(f"\n{'='*60}")
    print(f"📊 Minecraft Rewind - Comparison Report")
    print(f"{'='*60}")
    player_name = snapshots[0].get("player_name")
    display_name = f"{player_name} ({player_uuid})" if player_name else player_uuid
    print(f"Player: {display_name}")
    print(f"Period: {comparison['from_date']} → {comparison['to_date']}")
    print(f"{'='*60}\n")
    
    print("📈 Statistics Evolution:\n")
    
    stat_labels = {
        "playtime_hours": "⏱️  Temps de jeu (heures)",
        "distance_km": "🏃 Distance parcourue (km)",
        "mob_kills": "⚔️  Mobs tués",
        "blocks_mined": "⛏️  Blocs minés",
        "blocks_crafted": "🔨 Blocs craftés",
        "deaths": "💀 Morts",
        "tools_broken": "🔧 Outils cassés",
    }
    
    for key, label in stat_labels.items():
        if key in comparison["stats_diff"]:
            diff_data = comparison["stats_diff"][key]
            diff = diff_data["diff"]
            sign = "+" if diff > 0 else ""
            print(f"  {label}:")
            print(f"    {diff_data['from']} → {diff_data['to']} ({sign}{diff})")
            print()
    
    print(f"{'='*60}")
    print("🏆 Top Items (semaine actuelle):\n")
    
    for category, item_data in comparison["top_items_to"].items():
        if item_data["name"]:
            print(f"  Top {category}: {item_data['name']} ({item_data['count']}x)")
    
    print(f"\n{'='*60}\n")
    
    return 0


def cmd_export(args: argparse.Namespace) -> int:
    """Execute the export command.
    
    Exports player data in JSON or CSV format.
    """
    player_uuid = args.player
    output_format = args.format or "json"
    
    snapshots = get_latest_snapshots(player_uuid, limit=100)
    
    if not snapshots:
        logger.warning(f"No snapshots found for player {player_uuid}")
        return 1
    
    if output_format == "json":
        output = json.dumps(snapshots, indent=2, default=str)
        print(output)
        
    elif output_format == "csv":
        if not snapshots:
            return 0
            
        # Flatten data for CSV
        rows = []
        for snap in snapshots:
            row = {
                "player_uuid": snap["player_uuid"],
                "extraction_date": snap["extraction_date"],
                **snap.get("stats", {})
            }
            # Add top items
            for cat, item in snap.get("top_items", {}).items():
                row[f"top_{cat}"] = item.get("name", "")
                row[f"top_{cat}_count"] = item.get("count", 0)
            rows.append(row)
        
        if rows:
            writer = csv.DictWriter(sys.stdout, fieldnames=rows[0].keys())
            writer.writeheader()
            writer.writerows(rows)
    
    return 0


def cmd_list(args: argparse.Namespace) -> int:
    """List all players with snapshots."""
    players = get_all_players()
    
    if not players:
        print("No players found in database.")
        return 0
    
    print(f"\n{'='*60}")
    print(f"📋 Players with snapshots: {len(players)}")
    print(f"{'='*60}\n")
    
    for player in players:
        player_uuid = player["uuid"]
        player_name = player.get("name")
        snapshots = get_latest_snapshots(player_uuid, limit=1)
        last_date = snapshots[0]["extraction_date"] if snapshots else "N/A"
        
        if player_name:
            print(f"  • {player_name}")
            print(f"    UUID: {player_uuid}")
        else:
            print(f"  • {player_uuid}")
        print(f"    Dernière extraction: {last_date}")
        print()
    
    return 0


def main(argv: Optional[list[str]] = None) -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        prog="minecraft-rewind",
        description="Minecraft Rewind - Weekly Statistics System"
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # Snapshot command
    snap_parser = subparsers.add_parser(
        "snapshot",
        help="Create a new snapshot of all player stats"
    )
    snap_parser.add_argument(
        "--stats-dir",
        help="Path to Minecraft stats directory"
    )
    snap_parser.add_argument(
        "--date",
        help="Extraction date (YYYY-MM-DD), defaults to today"
    )
    snap_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Parse and display stats without saving"
    )
    
    # Compare command
    compare_parser = subparsers.add_parser(
        "compare",
        help="Compare snapshots for a player"
    )
    compare_parser.add_argument(
        "--player",
        required=True,
        help="Player UUID"
    )
    compare_parser.add_argument(
        "--weeks",
        type=int,
        default=2,
        help="Number of weeks to compare (default: 2)"
    )
    
    # Export command
    export_parser = subparsers.add_parser(
        "export",
        help="Export player data"
    )
    export_parser.add_argument(
        "--player",
        required=True,
        help="Player UUID"
    )
    export_parser.add_argument(
        "--format",
        choices=["json", "csv"],
        default="json",
        help="Output format (default: json)"
    )
    
    # List command
    subparsers.add_parser(
        "list",
        help="List all players with snapshots"
    )
    
    args = parser.parse_args(argv)
    
    if not args.command:
        parser.print_help()
        return 0
    
    commands = {
        "snapshot": cmd_snapshot,
        "compare": cmd_compare,
        "export": cmd_export,
        "list": cmd_list,
    }
    
    return commands[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
