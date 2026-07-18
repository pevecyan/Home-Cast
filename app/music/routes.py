import time
import logging
import threading

from flask import Blueprint, Response, request, jsonify, current_app

logger = logging.getLogger(__name__)

from app.music import ytmusic
from app.music import playlist as pl
from app.music import player
from app.music.player import PlayError
from app.music.downloader import get_cache
from app.devices import chromecast, sonos

# In-memory M3U store (generated playlists) — shared with the scheduler.
_m3u_store = player._m3u_store

music_bp = Blueprint("music", __name__, url_prefix="/music")


# --- Discover cache (home feed + moods) ---
# YouTube Music is slow and rate-limited; cache these read-only feeds so we
# don't re-fetch on every Discover open. TTL comes from config (cache.discover_ttl).
_discover_cache = {}          # key -> (expiry_epoch, value)
_discover_locks = {}          # key -> Lock (de-duplicate concurrent misses)
_discover_guard = threading.Lock()


def _discover_ttl():
    return current_app.config["APP"]["cache"].get("discover_ttl", 900)


def _cached_discover(key, fetch, force=False):
    """Return a cached value for `key`, or call `fetch()` and cache it.

    Single-flight per key so a burst of Discover opens triggers one YT request.
    Failures are not cached (they propagate so the caller can retry).
    When `force` is True, bypass any cached value and re-fetch (used by the
    Discover refresh button).
    """
    now = time.time()
    if not force:
        entry = _discover_cache.get(key)
        if entry and now < entry[0]:
            return entry[1]

    with _discover_guard:
        lock = _discover_locks.setdefault(key, threading.Lock())

    with lock:
        # Re-check: another thread may have populated it while we waited
        # (skip the shortcut on a forced refresh).
        if not force:
            entry = _discover_cache.get(key)
            if entry and time.time() < entry[0]:
                return entry[1]
        value = fetch()
        _discover_cache[key] = (time.time() + _discover_ttl(), value)
        return value


def _force_refresh():
    return request.args.get("refresh") in ("1", "true", "yes")


# --- Search ---

@music_bp.route("/search", methods=["GET"])
def search_music():
    query = request.args.get("q", "")
    filter_type = request.args.get("type", "songs")
    if not query:
        return jsonify({"error": "Missing query parameter 'q'"}), 400
    if filter_type not in ("songs", "artists", "playlists", "albums"):
        return jsonify({"error": "Invalid type. Use: songs, artists, playlists, albums"}), 400
    results = ytmusic.search(query, filter_type)
    return jsonify(results)


# --- Discover (home feed + moods) ---

@music_bp.route("/home", methods=["GET"])
def home_feed():
    """YouTube Music home feed: rows of playlist/album/song/artist cards."""
    try:
        return jsonify(_cached_discover("home", ytmusic.get_home, force=_force_refresh()))
    except Exception as e:
        logger.exception("Failed to fetch home feed")
        return jsonify({"error": str(e)}), 502


@music_bp.route("/moods", methods=["GET"])
def mood_categories():
    """Mood/genre chips shown at the top of Discover."""
    try:
        return jsonify(_cached_discover("moods", ytmusic.get_mood_categories, force=_force_refresh()))
    except Exception as e:
        logger.exception("Failed to fetch mood categories")
        return jsonify({"error": str(e)}), 502


@music_bp.route("/moods/<params>", methods=["GET"])
def mood_playlists(params):
    """Playlists for a selected mood/genre chip."""
    try:
        return jsonify(_cached_discover(f"moods:{params}", lambda: ytmusic.get_mood_playlists(params), force=_force_refresh()))
    except Exception as e:
        logger.exception("Failed to fetch mood playlists")
        return jsonify({"error": str(e)}), 502


@music_bp.route("/artist/<browse_id>", methods=["GET"])
def get_artist(browse_id):
    result = ytmusic.get_artist(browse_id)
    return jsonify(result)


@music_bp.route("/playlist/<playlist_id>", methods=["GET"])
def get_playlist(playlist_id):
    result = ytmusic.get_playlist_tracks(playlist_id)
    return jsonify(result)


@music_bp.route("/album/<browse_id>", methods=["GET"])
def get_album(browse_id):
    result = ytmusic.get_album(browse_id)
    return jsonify(result)


# --- Prefetch ---

@music_bp.route("/prefetch", methods=["POST"])
def prefetch():
    """Fire-and-forget background download of a song. Returns immediately."""
    data = request.json
    video_id = data.get("videoId")
    if not video_id:
        return jsonify({"error": "videoId is required"}), 400
    cache = get_cache()
    if cache.get_song_path(video_id):
        return jsonify({"status": "cached"})
    threading.Thread(target=_prefetch_song, args=(cache, video_id), daemon=True).start()
    return jsonify({"status": "prefetching"})


def _prefetch_song(cache, video_id):
    try:
        cache.ensure_song(video_id)
        logger.info("Prefetch complete: %s", video_id)
    except Exception as e:
        logger.debug("Prefetch failed for %s: %s", video_id, e)


# --- Play ---

@music_bp.route("/play", methods=["POST"])
def play():
    """Play a song or playlist on a speaker.

    Body: { slug, type, videoId } or { slug, type, playlistId }
    """
    data = request.json
    slug = data.get("slug")
    device_type = data.get("type", "chromecast")
    video_id = data.get("videoId")
    playlist_id = data.get("playlistId")
    track_list = data.get("tracks")  # explicit ordered track list (e.g. handoff from local browser play)
    start_index = data.get("startIndex", 0)
    shuffle = data.get("shuffle", False)
    repeat = data.get("repeat", "off")

    if not slug:
        return jsonify({"error": "Missing 'slug'"}), 400
    if not video_id and not playlist_id and not track_list:
        return jsonify({"error": "Provide 'videoId', 'playlistId', or 'tracks'"}), 400

    # resolve tracks
    if track_list:
        tracks = [{
            "videoId": t.get("videoId"),
            "title": t.get("title"),
            "artists": t.get("artists", []),
            "album": t.get("album"),
            "thumbnail": t.get("thumbnail"),
            "duration": t.get("duration"),
        } for t in track_list if t.get("videoId")]
        if not tracks:
            return jsonify({"error": "No playable tracks"}), 400
        # Rotate so the requested start track plays first (queue order preserved after it).
        if 0 < start_index < len(tracks):
            tracks = tracks[start_index:] + tracks[:start_index]
    elif video_id:
        track_meta = data.get("track") or {}
        tracks = [{
            "videoId": video_id,
            "title": track_meta.get("title"),
            "artists": track_meta.get("artists", []),
            "album": track_meta.get("album"),
            "thumbnail": track_meta.get("thumbnail"),
            "duration": track_meta.get("duration"),
        }]
    else:
        yt_playlist = ytmusic.get_playlist_tracks(playlist_id)
        tracks = yt_playlist.get("tracks", [])
        if not tracks:
            return jsonify({"error": "Playlist is empty"}), 400

    cache = get_cache()
    hostname = current_app.config["APP"]["hostname"]

    # download first track synchronously
    first = tracks[0]
    print(f"Downloading first track: {first.get('videoId')} - {first.get('title')}")
    try:
        path = cache.ensure_song(first["videoId"])
        print(f"Downloaded to: {path}")
    except RuntimeError as e:
        print(f"Download failed: {e}")
        return jsonify({"error": f"Failed to download first track: {e}"}), 500

    # start background downloads for remaining tracks
    if len(tracks) > 1:
        remaining = tracks[1:]
        threading.Thread(
            target=_download_remaining,
            args=(cache, remaining),
            daemon=True,
        ).start()

    # generate M3U
    m3u_content = pl.generate_m3u(tracks[:5], hostname)

    # serve M3U at a predictable URL
    m3u_id = playlist_id or first["videoId"]
    _m3u_store[m3u_id] = m3u_content
    m3u_url = f"{hostname}/music/m3u/{m3u_id}.m3u"
    print(f"Generated M3U for {len(tracks)} tracks at {m3u_url}")

    # send to speaker
    if device_type == "sonos":
        device = sonos.get_by_slug(slug)
        if not device:
            return jsonify({"error": "Sonos device not found"}), 400
        sonos.play_media(device, m3u_url)
        if shuffle:
            sonos.set_shuffle(device, True)
        if repeat != "off":
            sonos.set_repeat(device, repeat)
    else:
        cc = chromecast.get_by_slug(slug)
        if not cc:
            return jsonify({"error": "Chromecast device not found"}), 400
        cast_app_id = current_app.config["APP"].get("cast_app_id")
        queue = chromecast.get_queue(slug, cc, cache, cast_app_id=cast_app_id)
        queue.load(tracks, shuffle=shuffle, repeat=repeat)

    return jsonify({
        "status": "playing",
        "trackCount": len(tracks),
    })


@music_bp.route("/transfer", methods=["POST"])
def transfer():
    """Transfer active queue from one speaker to another, starting at current track."""
    data = request.json
    from_slug = data.get("fromSlug")
    to_slug = data.get("toSlug")
    to_type = data.get("toType", "chromecast")

    if not from_slug or not to_slug:
        return jsonify({"error": "fromSlug and toSlug are required"}), 400

    # Only Chromecast queues are transferable
    queue = chromecast.get_queue(from_slug)
    if not queue or not queue.tracks:
        return jsonify({"error": "No active queue on source device"}), 400

    tracks = queue._shuffled_tracks or queue.tracks
    repeat = queue.repeat

    cache = get_cache()

    # Stop source
    cc_from = chromecast.get_by_slug(from_slug)
    if cc_from:
        chromecast.stop(cc_from)

    # Start on target
    if to_type == "sonos":
        hostname = current_app.config["APP"]["hostname"]
        m3u_content = pl.generate_m3u(tracks, hostname)
        transfer_id = f"transfer_{to_slug}"
        _m3u_store[transfer_id] = m3u_content
        m3u_url = f"{hostname}/music/m3u/{transfer_id}.m3u"
        device = sonos.get_by_slug(to_slug)
        if not device:
            return jsonify({"error": "Target Sonos device not found"}), 400
        sonos.play_media(device, m3u_url)
        if repeat != "off":
            sonos.set_repeat(device, repeat)
    else:
        cc_to = chromecast.get_by_slug(to_slug)
        if not cc_to:
            return jsonify({"error": "Target Chromecast device not found"}), 400
        cast_app_id = current_app.config["APP"].get("cast_app_id")
        new_queue = chromecast.get_queue(to_slug, cc_to, cache, cast_app_id=cast_app_id)
        new_queue.load(tracks, repeat=repeat)

    from app.ws import broadcast_states
    broadcast_states()
    return jsonify({"status": "transferred", "trackCount": len(tracks)})


@music_bp.route("/m3u/<m3u_id>.m3u", methods=["GET"])
def serve_m3u(m3u_id):
    content = _m3u_store.get(m3u_id)
    if not content:
        return jsonify({"error": "M3U not found"}), 404
    return Response(content, mimetype="audio/x-mpegurl")


@music_bp.route("/m3u/<m3u_id>.m3u8", methods=["GET"])
def serve_m3u8(m3u_id):
    content = _m3u_store.get(m3u_id)
    if not content:
        return jsonify({"error": "M3U not found"}), 404
    return Response(content, mimetype="application/vnd.apple.mpegurl")


def _download_remaining(cache, tracks):
    for t in tracks:
        vid = t.get("videoId")
        if vid:
            try:
                cache.ensure_song(vid)
            except Exception:
                pass


# --- Persisted playlists ---

@music_bp.route("/playlists", methods=["GET"])
def list_playlists():
    return jsonify(pl.list_playlists())


@music_bp.route("/playlists", methods=["POST"])
def create_playlist():
    data = request.json
    name = data.get("name", "Untitled")
    tracks = data.get("tracks", [])
    author = data.get("author")
    cover_url = data.get("coverUrl")
    result = pl.create_playlist(name, tracks, author=author, cover_url=cover_url)
    return jsonify(result), 201


@music_bp.route("/playlists/<playlist_id>", methods=["GET"])
def get_saved_playlist(playlist_id):
    result = pl.get_playlist(playlist_id)
    if not result:
        return jsonify({"error": "Playlist not found"}), 404
    return jsonify(result)


@music_bp.route("/playlists/<playlist_id>", methods=["PUT"])
def update_playlist(playlist_id):
    data = request.json
    result = pl.update_playlist(playlist_id, name=data.get("name"), tracks=data.get("tracks"))
    if not result:
        return jsonify({"error": "Playlist not found"}), 404
    return jsonify(result)


@music_bp.route("/playlists/<playlist_id>", methods=["DELETE"])
def delete_playlist(playlist_id):
    pl.delete_playlist(playlist_id)
    return jsonify({"status": "deleted"})


@music_bp.route("/playlists/<playlist_id>/play", methods=["POST"])
def play_saved_playlist(playlist_id):
    data = request.json
    slug = data.get("slug")
    device_type = data.get("type", "chromecast")
    shuffle = data.get("shuffle", False)
    repeat = data.get("repeat", "off")

    try:
        result = player.play_saved_playlist(
            current_app.config["APP"], playlist_id, slug, device_type,
            shuffle=shuffle, repeat=repeat,
        )
    except PlayError as e:
        msg = str(e)
        status = 404 if msg == "Playlist not found" else 400
        return jsonify({"error": msg}), status
    return jsonify(result)
