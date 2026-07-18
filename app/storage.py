"""Simple JSON file storage for favorites, recents, settings and alarms."""

import json
import uuid
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

DATA_DIR = Path("data")

FAVORITES_FILE = DATA_DIR / "favorite_radios.json"
RECENTS_FILE = DATA_DIR / "recents.json"
SETTINGS_FILE = DATA_DIR / "settings.json"
ALARMS_FILE = DATA_DIR / "alarms.json"

MAX_RECENTS = 12

_SETTINGS_DEFAULTS = {"sleepEnabled": True, "volumeLockEnabled": True}


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


# --- Settings ---

def get_settings():
    if not SETTINGS_FILE.exists():
        return dict(_SETTINGS_DEFAULTS)
    with open(SETTINGS_FILE) as f:
        return {**_SETTINGS_DEFAULTS, **json.load(f)}


def save_settings(data):
    allowed = set(_SETTINGS_DEFAULTS.keys())
    merged = {**get_settings(), **{k: v for k, v in data.items() if k in allowed}}
    _ensure_dir()
    with open(SETTINGS_FILE, "w") as f:
        json.dump(merged, f, indent=2)
    return merged


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


# --- Alarms ---
#
# An alarm is a dict:
#   id       str            uuid
#   time     "HH:MM"        24h local time to fire
#   days     [int]          weekday mask, Mon=0..Sun=6; [] = one-shot
#   target   {slug, type}   a single speaker, or {"slug": "all", "type": ...}
#   action   {kind, ref, name?}
#              kind == "playlist" -> ref is a saved-playlist id
#              kind == "radio"    -> ref is a favorite station's stationuuid
#   shuffle  bool
#   repeat   "off"|"all"|"one"
#   volume   float|None     0..1, applied before play if set
#   fadeIn   int            seconds to ramp volume over (0 = no fade)
#   enabled  bool

_ALARM_DEFAULTS = {
    "time": "07:00",
    "days": [],
    "target": {"slug": "all", "type": "all"},
    "action": {"kind": "playlist", "ref": None},
    "shuffle": False,
    "repeat": "off",
    "volume": None,
    "fadeIn": 0,
    "enabled": True,
}


def get_alarms():
    return _load(ALARMS_FILE)


def _sanitize_alarm(data, existing=None):
    """Merge incoming fields over defaults/existing, keeping only known keys."""
    base = dict(existing) if existing else dict(_ALARM_DEFAULTS)
    for k in _ALARM_DEFAULTS:
        if k in data:
            base[k] = data[k]
    return base


def add_alarm(data):
    alarms = get_alarms()
    alarm = _sanitize_alarm(data)
    alarm["id"] = str(uuid.uuid4())
    alarms.append(alarm)
    _save(ALARMS_FILE, alarms)
    return alarm


def update_alarm(alarm_id, data):
    alarms = get_alarms()
    for i, a in enumerate(alarms):
        if a["id"] == alarm_id:
            merged = _sanitize_alarm(data, existing=a)
            merged["id"] = alarm_id
            alarms[i] = merged
            _save(ALARMS_FILE, alarms)
            return merged
    return None


def delete_alarm(alarm_id):
    alarms = [a for a in get_alarms() if a["id"] != alarm_id]
    _save(ALARMS_FILE, alarms)
    return alarms


def set_alarm_enabled(alarm_id, enabled):
    return update_alarm(alarm_id, {"enabled": bool(enabled)})
