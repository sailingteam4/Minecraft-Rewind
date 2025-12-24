"""Flask routes for Minecraft Rewind web interface."""

from flask import Blueprint, render_template, jsonify, request, redirect, url_for
from web.queries import (
    get_all_leaderboards,
    get_global_stats,
    get_player_list,
    get_player_by_name,
    get_player_stats,
    get_player_history,
    get_player_ranks,
)

bp = Blueprint('main', __name__)


@bp.route('/')
def index():
    """Global rewind page with leaderboards."""
    leaderboards = get_all_leaderboards()
    global_stats = get_global_stats()
    players = get_player_list()
    
    return render_template('index.html',
                           leaderboards=leaderboards,
                           global_stats=global_stats,
                           players=players)


@bp.route('/player/<pseudo>')
def player_detail(pseudo: str):
    """Personal rewind page for a specific player."""
    # Find player by name
    player_info = get_player_by_name(pseudo)
    
    if not player_info:
        return render_template('player_not_found.html', pseudo=pseudo), 404
    
    # Get player stats
    player_data = get_player_stats(player_info["uuid"])
    if not player_data:
        return render_template('player_not_found.html', pseudo=pseudo), 404
    
    # Get history and ranks
    history = get_player_history(player_info["uuid"], 10)
    ranks = get_player_ranks(player_info["uuid"])
    players = get_player_list()
    
    return render_template('player.html',
                           player=player_data,
                           history=history,
                           ranks=ranks,
                           players=players)


@bp.route('/search')
def search():
    """Handle player search form."""
    pseudo = request.args.get('pseudo', '').strip()
    if pseudo:
        return redirect(url_for('main.player_detail', pseudo=pseudo))
    return redirect(url_for('main.index'))


@bp.route('/api/players')
def api_players():
    """JSON endpoint for player list (autocomplete)."""
    players = get_player_list()
    return jsonify(players)


@bp.route('/avatar/<pseudo>')
@bp.route('/avatar/<pseudo>/<int:size>')
def avatar_proxy(pseudo: str, size: int = 64):
    """Proxy for Minecraft avatars to avoid CORS issues."""
    import urllib.request
    from flask import Response
    
    # Try Crafatar first (better CORS support), fallback to mc-heads
    urls = [
        f"https://crafatar.com/avatars/{pseudo}?size={size}&overlay",
        f"https://mc-heads.net/avatar/{pseudo}/{size}",
        f"https://minotar.net/helm/{pseudo}/{size}.png",
    ]
    
    for url in urls:
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=5) as response:
                image_data = response.read()
                return Response(image_data, mimetype='image/png')
        except Exception:
            continue
    
    # Return a placeholder if all fail
    return redirect(f"https://ui-avatars.com/api/?name={pseudo}&background=4AEDD9&color=1a1a2e&size={size}")

