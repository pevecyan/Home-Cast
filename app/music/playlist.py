import json
import uuid
import base64
import logging
from pathlib import Path

import requests

logger = logging.getLogger(__name__)

PLAYLISTS_FILE = Path("data/playlists.json")

# Cap the stored cover so playlists.json doesn't bloat with a huge image.
_COVER_MAX_BYTES = 2 * 1024 * 1024  # 2 MB
_COVER_TIMEOUT = 10  # seconds


def _fetch_cover_base64(tracks):
    """Return a base64 data URI for the first track that has a fetchable
    thumbnail, or None. For custom playlists this naturally uses the first
    song we can get a picture of.
    """
    for track in tracks or []:
        url = track.get("thumbnail")
        if not url:
            continue
        try:
            resp = requests.get(url, timeout=_COVER_TIMEOUT)
            resp.raise_for_status()
            content = resp.content
            if not content or len(content) > _COVER_MAX_BYTES:
                continue
            mime = resp.headers.get("Content-Type", "image/jpeg").split(";")[0].strip()
            if not mime.startswith("image/"):
                mime = "image/jpeg"
            encoded = base64.b64encode(content).decode("ascii")
            return f"data:{mime};base64,{encoded}"
        except Exception as e:
            logger.debug("Failed to fetch cover from %s: %s", url, e)
            continue
    return None


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


def _track_ids(tracks):
    return [t.get("videoId") for t in (tracks or []) if t.get("videoId")]


def pinned_video_ids():
    """Return the set of videoIds referenced by any saved playlist.

    These songs are kept in the cache indefinitely so playlists start playing
    immediately. Registered with the SongCache as its pin provider.
    """
    ids = set()
    for pl in _load_playlists():
        ids.update(_track_ids(pl.get("tracks")))
    return ids


def _prewarm(tracks):
    """Kick off background downloads for a playlist's tracks. Imported lazily
    to avoid a circular import at module load."""
    try:
        from app.music.downloader import get_cache
        get_cache().prewarm(_track_ids(tracks))
    except Exception:
        logger.exception("Failed to prewarm playlist tracks")


def _evict(video_ids):
    """Drop cached files for tracks no longer referenced by any playlist."""
    try:
        from app.music.downloader import get_cache
        get_cache().evict_unpinned(video_ids)
    except Exception:
        logger.exception("Failed to evict orphaned tracks")


def create_playlist(name, tracks=None):
    playlists = _load_playlists()
    tracks = tracks or []
    pl = {
        "id": str(uuid.uuid4()),
        "name": name,
        "tracks": tracks,
        "cover": _fetch_cover_base64(tracks),
    }
    playlists.append(pl)
    _save_playlists(playlists)
    _prewarm(tracks)
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
            old_ids = set(_track_ids(pl.get("tracks")))
            if name is not None:
                pl["name"] = name
            if tracks is not None:
                pl["tracks"] = tracks
                # (Re)compute the cover when it's missing -- e.g. a custom
                # playlist that just got its first song with a picture.
                if not pl.get("cover"):
                    pl["cover"] = _fetch_cover_base64(tracks)
            _save_playlists(playlists)
            if tracks is not None:
                new_ids = set(_track_ids(tracks))
                _prewarm([t for t in tracks if t.get("videoId") not in old_ids])
                _evict(old_ids - new_ids)
            return pl
    return None


def delete_playlist(playlist_id):
    playlists = _load_playlists()
    removed = [pl for pl in playlists if pl["id"] == playlist_id]
    playlists = [pl for pl in playlists if pl["id"] != playlist_id]
    _save_playlists(playlists)
    for pl in removed:
        _evict(_track_ids(pl.get("tracks")))
