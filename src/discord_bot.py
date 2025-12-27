"""Discord bot for displaying Minecraft Rewind stats."""

import discord
from discord import app_commands
from discord.ext import commands
import aiohttp
from datetime import datetime
from typing import Optional
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import DISCORD_TOKEN, DISCORD_GUILD_ID
from src.database import get_all_players, get_latest_snapshots


class MinecraftRewindBot(commands.Bot):
    """Discord bot for Minecraft Rewind stats."""
    
    def __init__(self):
        intents = discord.Intents.default()
        super().__init__(command_prefix="!", intents=intents)
        
    async def setup_hook(self):
        """Called when the bot is ready to sync commands."""
        if DISCORD_GUILD_ID:
            guild = discord.Object(id=int(DISCORD_GUILD_ID))
            self.tree.copy_global_to(guild=guild)
            await self.tree.sync(guild=guild)
            print(f"✅ Commands synced to guild {DISCORD_GUILD_ID}")
        else:
            await self.tree.sync()
            print("✅ Commands synced globally (may take up to 1 hour)")


bot = MinecraftRewindBot()


async def get_mcheads_avatar(username: str) -> Optional[str]:
    """Check if player has a premium account and return avatar URL.
    
    Args:
        username: Minecraft username
        
    Returns:
        Avatar URL if premium, None otherwise
    """
    if not username:
        return None
        
    url = f"https://api.mcheads.org/avatar/{username}/left/256"
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.head(url, timeout=aiohttp.ClientTimeout(total=5)) as response:
                if response.status == 200:
                    return url
    except Exception:
        pass
    
    return None


def format_number(num: float) -> str:
    """Format a number with French thousands separator."""
    if isinstance(num, float):
        if num == int(num):
            return f"{int(num):,}".replace(",", " ")
        return f"{num:,.2f}".replace(",", " ")
    return f"{num:,}".replace(",", " ")


def format_item_name(name: Optional[str]) -> str:
    """Format Minecraft item name for display."""
    if not name:
        return "Aucun"
    return name.replace("_", " ").title()


@bot.event
async def on_ready():
    """Called when the bot is ready."""
    print(f"🎮 {bot.user} est connecté et prêt!")
    print(f"📊 Serveurs: {len(bot.guilds)}")
    

@bot.tree.command(name="stats", description="📊 Affiche les statistiques globales du serveur Minecraft")
@app_commands.checks.has_permissions(administrator=True)
async def stats_command(interaction: discord.Interaction):
    """Display global server statistics."""
    await interaction.response.defer()
    
    try:
        players = get_all_players()
        
        if not players:
            embed = discord.Embed(
                title="📊 Statistiques du Serveur",
                description="❌ Aucune donnée disponible dans la base de données.",
                color=discord.Color.red()
            )
            await interaction.followup.send(embed=embed)
            return
        
        # Collect all player stats
        all_stats = []
        totals = {
            "playtime_hours": 0,
            "distance_km": 0,
            "mob_kills": 0,
            "blocks_mined": 0,
            "blocks_crafted": 0,
            "deaths": 0,
            "tools_broken": 0
        }
        
        for player in players:
            snapshots = get_latest_snapshots(player["uuid"], limit=1)
            if snapshots:
                latest = snapshots[0]
                player_stats = latest.get("stats", {})
                player_name = latest.get("player_name") or player.get("name") or player["uuid"][:8]
                
                all_stats.append({
                    "name": player_name,
                    "playtime": player_stats.get("playtime_hours", 0),
                    "uuid": player["uuid"]
                })
                
                for key in totals:
                    totals[key] += player_stats.get(key, 0)
        
        # Sort by playtime
        all_stats.sort(key=lambda x: x["playtime"], reverse=True)
        
        # Create embed
        embed = discord.Embed(
            title="📊 Statistiques du Serveur Minecraft",
            color=discord.Color.green(),
            timestamp=datetime.now()
        )
        
        # Player count
        embed.add_field(
            name="👥 Joueurs",
            value=f"**{len(players)}** joueurs enregistrés",
            inline=False
        )
        
        # Top players by playtime
        if all_stats:
            top_list = []
            for i, player in enumerate(all_stats[:5], 1):
                medal = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣"][i-1]
                top_list.append(f"{medal} **{player['name']}** - {format_number(player['playtime'])}h")
            
            embed.add_field(
                name="🏆 Top Joueurs (Temps de jeu)",
                value="\n".join(top_list),
                inline=False
            )
        
        # Server totals
        totals_text = f"""
⏱️ **Temps de jeu total:** {format_number(totals['playtime_hours'])}h
📏 **Distance parcourue:** {format_number(totals['distance_km'])} km
⚔️ **Mobs tués:** {format_number(totals['mob_kills'])}
⛏️ **Blocs minés:** {format_number(totals['blocks_mined'])}
🛠️ **Blocs craftés:** {format_number(totals['blocks_crafted'])}
💀 **Morts:** {format_number(totals['deaths'])}
🔧 **Outils cassés:** {format_number(totals['tools_broken'])}
        """.strip()
        
        embed.add_field(
            name="📈 Totaux du Serveur",
            value=totals_text,
            inline=False
        )
        
        embed.set_footer(text="Minecraft Rewind • Dernière extraction")
        
        await interaction.followup.send(embed=embed)
        
    except Exception as e:
        embed = discord.Embed(
            title="❌ Erreur",
            description=f"Une erreur est survenue: {str(e)}",
            color=discord.Color.red()
        )
        await interaction.followup.send(embed=embed)


@bot.tree.command(name="playerstats", description="📋 Affiche les statistiques détaillées d'un joueur")
@app_commands.describe(player_name="Nom du joueur Minecraft")
@app_commands.checks.has_permissions(administrator=True)
async def playerstats_command(interaction: discord.Interaction, player_name: str):
    """Display detailed stats for a specific player."""
    await interaction.response.defer()
    
    try:
        players = get_all_players()
        
        # Find player by name (case insensitive)
        target_player = None
        for player in players:
            name = player.get("name") or ""
            if name.lower() == player_name.lower():
                target_player = player
                break
        
        if not target_player:
            # Try partial match
            for player in players:
                name = player.get("name") or ""
                if player_name.lower() in name.lower():
                    target_player = player
                    break
        
        if not target_player:
            embed = discord.Embed(
                title="❌ Joueur non trouvé",
                description=f"Aucun joueur nommé **{player_name}** n'a été trouvé.\n\n"
                           f"**Joueurs disponibles:**\n" + 
                           "\n".join([f"• {p.get('name') or p['uuid'][:8]}" for p in players[:10]]),
                color=discord.Color.red()
            )
            await interaction.followup.send(embed=embed)
            return
        
        # Get latest snapshot
        snapshots = get_latest_snapshots(target_player["uuid"], limit=1)
        
        if not snapshots:
            embed = discord.Embed(
                title="❌ Aucune donnée",
                description=f"Aucune statistique disponible pour **{player_name}**.",
                color=discord.Color.red()
            )
            await interaction.followup.send(embed=embed)
            return
        
        latest = snapshots[0]
        stats = latest.get("stats", {})
        top_items = latest.get("top_items", {})
        display_name = latest.get("player_name") or target_player.get("name") or player_name
        
        # Create embed
        embed = discord.Embed(
            title=f"📋 Stats de {display_name}",
            color=discord.Color.gold(),
            timestamp=datetime.now()
        )
        
        # Try to get avatar
        avatar_url = await get_mcheads_avatar(display_name)
        if avatar_url:
            embed.set_thumbnail(url=avatar_url)
        
        # General stats
        general_stats = f"""
⏱️ **Temps de jeu:** {format_number(stats.get('playtime_hours', 0))}h
📏 **Distance:** {format_number(stats.get('distance_km', 0))} km
⚔️ **Mobs tués:** {format_number(stats.get('mob_kills', 0))}
⛏️ **Blocs minés:** {format_number(stats.get('blocks_mined', 0))}
🛠️ **Blocs craftés:** {format_number(stats.get('blocks_crafted', 0))}
💀 **Morts:** {format_number(stats.get('deaths', 0))}
🔧 **Outils cassés:** {format_number(stats.get('tools_broken', 0))}
        """.strip()
        
        embed.add_field(
            name="📊 Statistiques Générales",
            value=general_stats,
            inline=False
        )
        
        # Top items
        if top_items:
            mined = top_items.get("mined", {})
            killed = top_items.get("killed", {})
            crafted = top_items.get("crafted", {})
            broken = top_items.get("broken", {})
            
            top_items_text = f"""
⛏️ **Plus miné:** {format_item_name(mined.get('name'))} ({format_number(mined.get('count', 0))})
🗡️ **Plus tué:** {format_item_name(killed.get('name'))} ({format_number(killed.get('count', 0))})
🛠️ **Plus crafté:** {format_item_name(crafted.get('name'))} ({format_number(crafted.get('count', 0))})
🔧 **Plus cassé:** {format_item_name(broken.get('name'))} ({format_number(broken.get('count', 0))})
            """.strip()
            
            embed.add_field(
                name="🏆 Top Items",
                value=top_items_text,
                inline=False
            )
        
        # Extraction date
        extraction_date = latest.get("extraction_date", "Inconnue")
        embed.set_footer(text=f"Minecraft Rewind • Snapshot du {extraction_date}")
        
        await interaction.followup.send(embed=embed)
        
    except Exception as e:
        embed = discord.Embed(
            title="❌ Erreur",
            description=f"Une erreur est survenue: {str(e)}",
            color=discord.Color.red()
        )
        await interaction.followup.send(embed=embed)


@stats_command.error
@playerstats_command.error
async def admin_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    """Handle permission errors for admin commands."""
    if isinstance(error, app_commands.MissingPermissions):
        embed = discord.Embed(
            title="🔒 Accès Refusé",
            description="Cette commande est réservée aux **administrateurs** du serveur.",
            color=discord.Color.red()
        )
        if interaction.response.is_done():
            await interaction.followup.send(embed=embed, ephemeral=True)
        else:
            await interaction.response.send_message(embed=embed, ephemeral=True)
    else:
        raise error


def run_bot():
    """Run the Discord bot."""
    if not DISCORD_TOKEN:
        print("❌ DISCORD_TOKEN non configuré!")
        print("   Définissez la variable d'environnement DISCORD_TOKEN")
        return
    
    print("🚀 Démarrage du bot Minecraft Rewind...")
    bot.run(DISCORD_TOKEN)


if __name__ == "__main__":
    run_bot()
