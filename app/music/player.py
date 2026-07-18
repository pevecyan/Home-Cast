"""Shared playback helpers.

The play logic used to live inline in the route handlers, which meant it could
only run inside an HTTP request (it read ``current_app`` directly). The alarm
scheduler fires from a background thread with no request context, so these
helpers take an explicit ``config`` dict and are safe to call from anywhere:
route handlers pass ``current_app.config["APP"]``; the scheduler passes the
config it captured at startup.

Each helper returns a small result dict; device-not-found and empty-source
conditions raise ``PlayError`` so callers can translate to an HTTP status or
just log it.
"""

import logging
import threading

from app.music import playlist as pl
from app.music.downloader import get_cache
from app.devices import chromecast, sonos

logger = logging.getLogger(__name__)


class PlayError(Exception):
    """Raised when playback cannot start (device missing, empty source, etc.)."""


def _download_remaining(cache, tracks):
    for t in tracks:
        vid = t.get("videoId")
        if vid:
            try:
                cache.ensure_song(vid)
            except Exception:
                pass


def _play_tracks_on_device(config, slug, device_type, tracks, m3u_id,
                           shuffle=False, repeat="off"):
    """Load an ordered track list onto a speaker.

    Downloads the first track synchronously, warms the rest in the background,
    then hands off to Chromecast (queue) or Sonos (generated M3U). Shared by the
    saved-playlist play path and the alarm scheduler.
    """
    if not tracks:
        raise PlayError("No playable tracks")

    cache = get_cache()
    hostname = config["hostname"]

    # download first track synchronously so playback starts immediately
    try:
        cache.ensure_song(tracks[0]["videoId"])
    except RuntimeError as e:
        raise PlayError(f"Failed to download first track: {e}")

    if len(tracks) > 1:
        threading.Thread(
            target=_download_remaining,
            args=(cache, tracks[1:]),
            daemon=True,
        ).start()

    if device_type == "sonos":
        device = sonos.get_by_slug(slug)
        if not device:
            raise PlayError("Sonos device not found")
        m3u_content = pl.generate_m3u(tracks, hostname)
        set_m3u(m3u_id, m3u_content)
        m3u_url = f"{hostname.rstrip('/')}/music/m3u/{m3u_id}.m3u"
        sonos.play_media(device, m3u_url)
        if shuffle:
            sonos.set_shuffle(device, True)
        if repeat != "off":
            sonos.set_repeat(device, repeat)
    else:
        cc = chromecast.get_by_slug(slug)
        if not cc:
            raise PlayError("Chromecast device not found")
        cast_app_id = config.get("cast_app_id")
        queue = chromecast.get_queue(slug, cc, cache, cast_app_id=cast_app_id)
        queue.load(tracks, shuffle=shuffle, repeat=repeat)

    return {"status": "playing", "trackCount": len(tracks)}


def _with_fallback_cover(tracks, cover):
    """Give every track without its own thumbnail the playlist cover.

    Mirrors the UI's local-play fallback so cast/queue art (full-screen player,
    speaker card, cast receiver) shows the stored base64 playlist cover when a
    song's own thumbnail is missing or fails to load.
    """
    if not cover:
        return tracks
    return [t if t.get("thumbnail") else {**t, "thumbnail": cover} for t in tracks]


def play_saved_playlist(config, playlist_id, slug, device_type,
                        shuffle=False, repeat="off"):
    """Play a saved playlist (data/playlists.json) on a speaker."""
    saved = pl.get_playlist(playlist_id)
    if not saved:
        raise PlayError("Playlist not found")
    tracks = saved.get("tracks", [])
    if not tracks:
        raise PlayError("Playlist is empty")
    tracks = _with_fallback_cover(tracks, saved.get("cover"))
    return _play_tracks_on_device(
        config, slug, device_type, tracks, playlist_id,
        shuffle=shuffle, repeat=repeat,
    )


def play_radio(slug, device_type, station_url, station_name="Radio",
               station_favicon=None):
    """Play an internet radio stream on a speaker."""
    if device_type == "sonos":
        device = sonos.get_by_slug(slug)
        if not device:
            raise PlayError("Sonos device not found")
        sonos.play_media(device, station_url)
    else:
        cc = chromecast.get_by_slug(slug)
        if not cc:
            raise PlayError("Chromecast device not found")
        metadata = {
            "metadataType": 0,
            "title": station_name,
            "images": [{"url": station_favicon}] if station_favicon else [],
        }
        cc.media_controller.play_media(
            station_url,
            "audio/mpeg",
            title=station_name,
            thumb=station_favicon,
            metadata=metadata,
            stream_type="LIVE",
        )
        cc.media_controller.block_until_active()
    return {"status": "playing", "station": station_name}


# --- In-memory M3U store (generated playlists) ---
# Lives here so both the routes and the scheduler share one store.
_m3u_store = {}


def set_m3u(m3u_id, content):
    _m3u_store[m3u_id] = content


def get_m3u(m3u_id):
    return _m3u_store.get(m3u_id)
