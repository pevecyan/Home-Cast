import json
import uuid
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

PLAYLISTS_FILE = Path("data/playlists.json")


def generate_m3u(tracks, hostname):
    """Generate an extended M3U playlist string.

    tracks: list of dicts with videoId, title, artists, duration
    hostname: base URL like "http://192.168.1.100:5000"
    """
    hostname = hostname.rstrip("/")
    lines = ["#EXTM3U"]
    for t in tracks:
        video_id = t.get("videoId")
        if not video_id:
            continue
        title = t.get("title", "Unknown")
        artists = ", ".join(t.get("artists", []))
        display = f"{artists} - {title}" if artists else title
        duration = _parse_duration(t.get("duration", "0"))
        lines.append(f"#EXTINF:{duration},{display}")
        lines.append(f"{hostname}/media/{video_id}.mp3")
    return "\n".join(lines) + "\n"


def _parse_duration(duration_str):
    """Parse "3:45" or "1:02:30" to seconds."""
    if not duration_str or duration_str == "0":
        return -1
    parts = str(duration_str).split(":")
    try:
        if len(parts) == 3:
            return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
        elif len(parts) == 2:
            return int(parts[0]) * 60 + int(parts[1])
        return int(parts[0])
    except (ValueError, IndexError):
        return -1


# --- Persisted playlists ---

def _ensure_data_dir():
    PLAYLISTS_FILE.parent.mkdir(parents=True, exist_ok=True)


def _load_playlists():
    if not PLAYLISTS_FILE.exists():
        return []
    with open(PLAYLISTS_FILE) as f:
        return json.load(f)


def _save_playlists(playlists):
    _ensure_data_dir()
    with open(PLAYLISTS_FILE, "w") as f:
        json.dump(playlists, f, indent=2)


def list_playlists():
    return _load_playlists()


def create_playlist(name, tracks=None):
    playlists = _load_playlists()
    pl = {
        "id": str(uuid.uuid4()),
        "name": name,
        "tracks": tracks or [],
    }
    playlists.append(pl)
    _save_playlists(playlists)
    return pl


def get_playlist(playlist_id):
    for pl in _load_playlists():
        if pl["id"] == playlist_id:
            return pl
    return None


def update_playlist(playlist_id, name=None, tracks=None):
    playlists = _load_playlists()
    for pl in playlists:
        if pl["id"] == playlist_id:
            if name is not None:
                pl["name"] = name
            if tracks is not None:
                pl["tracks"] = tracks
            _save_playlists(playlists)
            return pl
    return None


def delete_playlist(playlist_id):
    playlists = _load_playlists()
    playlists = [pl for pl in playlists if pl["id"] != playlist_id]
    _save_playlists(playlists)
