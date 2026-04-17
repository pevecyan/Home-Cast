"""Simple JSON file storage for favorites and recents."""

import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

DATA_DIR = Path("data")

FAVORITES_FILE = DATA_DIR / "favorite_radios.json"
RECENTS_FILE = DATA_DIR / "recents.json"

MAX_RECENTS = 12


def _ensure_dir():
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def _load(path):
    if not path.exists():
        return []
    with open(path) as f:
        return json.load(f)


def _save(path, data):
    _ensure_dir()
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


# --- Favorite radios ---

def get_favorites():
    return _load(FAVORITES_FILE)


def add_favorite(station):
    favorites = get_favorites()
    if any(s["stationuuid"] == station["stationuuid"] for s in favorites):
        return favorites
    favorites.append(station)
    _save(FAVORITES_FILE, favorites)
    return favorites


def remove_favorite(stationuuid):
    favorites = [s for s in get_favorites() if s["stationuuid"] != stationuuid]
    _save(FAVORITES_FILE, favorites)
    return favorites


# --- Recents ---

def get_recents():
    return _load(RECENTS_FILE)


def add_recent(item):
    recents = get_recents()
    # Remove duplicate
    recents = [r for r in recents if not (r["id"] == item["id"] and r["type"] == item["type"])]
    recents.insert(0, item)
    recents = recents[:MAX_RECENTS]
    _save(RECENTS_FILE, recents)
    return recents
