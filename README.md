# 🎮 Minecraft Rewind - Système de Statistiques Hebdomadaires

Système automatisé pour extraire, stocker et comparer les statistiques des joueurs Minecraft chaque semaine.

## 📦 Installation

```bash
# Cloner le repo (si pas déjà fait)
cd /home/ubuntu/Minecraft-Rewind

# Pas de dépendances externes nécessaires - Python 3.10+ uniquement
python3 --version  # Vérifier Python >= 3.10
```

## ⚙️ Configuration

Éditer `config.py` pour définir les chemins :

```python
SERVER_DIR = Path("/var/lib/pufferpanel/servers/96c4c3ef")
STATS_DIR = SERVER_DIR / "world" / "stats"
USERCACHE_PATH = SERVER_DIR / "usercache.json"  # Pour les pseudos MC
```

Ou utiliser des variables d'environnement :

```bash
export MINECRAFT_SERVER_DIR="/path/to/server"
export MINECRAFT_STATS_DIR="/path/to/stats"
```

## 🚀 Utilisation

### Créer un Snapshot (extraction hebdomadaire)

```bash
# Snapshot de tous les joueurs
python -m src.rewind snapshot

# Avec un répertoire de stats personnalisé
python -m src.rewind snapshot --stats-dir /path/to/stats

# Mode dry-run (affiche sans sauvegarder)
python -m src.rewind snapshot --dry-run

# Spécifier une date d'extraction
python -m src.rewind snapshot --date 2024-01-15
```

### Comparer les Semaines

```bash
# Comparer les 2 derniers snapshots d'un joueur
python -m src.rewind compare --player 697664d1-56d9-306f-b7c9-ca1b6db16b78

# Comparer plus de semaines
python -m src.rewind compare --player <UUID> --weeks 4
```

### Exporter les Données

```bash
# Export JSON
python -m src.rewind export --player <UUID> --format json

# Export CSV
python -m src.rewind export --player <UUID> --format csv > data.csv
```

### Lister les Joueurs

```bash
python -m src.rewind list
```

## ⏰ Configuration Cron (Automatisation)

Pour exécuter automatiquement chaque dimanche à minuit :

```bash
# Éditer le crontab
crontab -e

# Ajouter cette ligne
0 0 * * 0 cd /home/ubuntu/Minecraft-Rewind && /usr/bin/python3 -m src.rewind snapshot >> /var/log/minecraft-rewind.log 2>&1
```

### Explication du cron

| Champ | Valeur | Description |
|-------|--------|-------------|
| `0` | Minute | À la minute 0 |
| `0` | Heure | À minuit |
| `*` | Jour du mois | Tous les jours |
| `*` | Mois | Tous les mois |
| `0` | Jour de la semaine | Dimanche (0 = dimanche) |

## 📊 Structure de la Base de Données

Les données sont stockées dans `data/rewind.db` (SQLite) :

```
snapshots/           # Un enregistrement par joueur par semaine
  ├── id
  ├── player_uuid
  ├── player_name    # Pseudo MC (depuis usercache.json)
  ├── extraction_date
  └── created_at

stats/               # Statistiques principales (clé-valeur)
  ├── snapshot_id
  ├── stat_key       # playtime_hours, distance_km, etc.
  └── stat_value

top_items/           # Meilleur item par catégorie
  ├── snapshot_id
  ├── category       # mined, killed, broken, crafted
  ├── item_name
  └── item_count
```

## 📈 Statistiques Extraites

| Statistique | Description | Source JSON |
|-------------|-------------|-------------|
| `playtime_hours` | Temps de jeu en heures | `minecraft:custom.minecraft:play_time` ÷ 72000 |
| `distance_km` | Distance totale (km) | Somme de tous les `*_one_cm` ÷ 100000 |
| `mob_kills` | Mobs tués | `minecraft:custom.minecraft:mob_kills` |
| `blocks_mined` | Blocs minés | Somme de `minecraft:mined` |
| `blocks_crafted` | Items craftés | Somme de `minecraft:crafted` |
| `deaths` | Nombre de morts | `minecraft:custom.minecraft:deaths` |
| `tools_broken` | Outils cassés | Somme de `minecraft:broken` |

### Top Items par Catégorie

- **Top miné** : Bloc le plus miné
- **Top tué** : Mob le plus tué
- **Top cassé** : Outil le plus usé
- **Top crafté** : Item le plus fabriqué

## 🗂 Structure des Fichiers

```
Minecraft-Rewind/
├── config.py              # Configuration
├── README.md              # Ce fichier
├── data/
│   └── rewind.db          # Base SQLite (créée automatiquement)
└── src/
    ├── __init__.py
    ├── stats_parser.py    # Extraction des stats JSON
    ├── database.py        # Gestion SQLite
    └── rewind.py          # CLI principal
```

## 🔧 Dépannage

### Erreur "Stats directory not found"

```bash
# Vérifier que le chemin existe
ls -la /var/lib/pufferpanel/servers/96c4c3ef/world/stats

# Ou définir le chemin en variable d'environnement
export MINECRAFT_STATS_DIR="/chemin/correct/vers/stats"
```

### Erreur "UNIQUE constraint failed"

Un snapshot existe déjà pour cette date. Utilisez `--date` pour une autre date ou supprimez l'ancien.

### Vérifier la base de données

```bash
sqlite3 data/rewind.db "SELECT * FROM snapshots;"
sqlite3 data/rewind.db "SELECT * FROM stats WHERE snapshot_id = 1;"
```

## 📝 Notes sur le Scoreboard Deaths

Le scoreboard `Deaths` que vous avez créé (`deathCount`) est synchronisé avec les stats vanilla. La valeur `minecraft:custom.minecraft:deaths` dans les fichiers JSON reflète automatiquement ce scoreboard.

## 🚧 Évolutions Futures

- [ ] Interface web pour visualiser les stats
- [ ] Génération de graphiques
- [ ] Export PDF du "Rewind"
- [ ] Notifications Discord
- [ ] Support multi-serveurs
