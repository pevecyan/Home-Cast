import threading

from flask import Blueprint, Response, request, jsonify, current_app

from app.music import ytmusic
from app.music import playlist as pl
from app.music.downloader import get_cache
from app.devices import chromecast, sonos

music_bp = Blueprint("music", __name__, url_prefix="/music")


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
    shuffle = data.get("shuffle", False)
    repeat = data.get("repeat", "off")

    if not slug:
        return jsonify({"error": "Missing 'slug'"}), 400
    if not video_id and not playlist_id:
        return jsonify({"error": "Provide 'videoId' or 'playlistId'"}), 400

    # resolve tracks
    if video_id:
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
        # Chromecast: play MP3s one by one via queue
        cc = chromecast.get_by_slug(slug)
        if not cc:
            return jsonify({"error": "Chromecast device not found"}), 400
        queue = chromecast.get_queue(slug, cc, cache)
        queue.load(tracks, shuffle=shuffle, repeat=repeat)

    return jsonify({
        "status": "playing",
        "trackCount": len(tracks),
    })


# In-memory M3U store (generated playlists)
_m3u_store = {}


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
    result = pl.create_playlist(name, tracks)
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

    saved = pl.get_playlist(playlist_id)
    if not saved:
        return jsonify({"error": "Playlist not found"}), 404

    tracks = saved.get("tracks", [])
    if not tracks:
        return jsonify({"error": "Playlist is empty"}), 400

    cache = get_cache()
    hostname = current_app.config["APP"]["hostname"]

    # download first track
    try:
        cache.ensure_song(tracks[0]["videoId"])
    except RuntimeError as e:
        return jsonify({"error": f"Failed to download: {e}"}), 500

    if len(tracks) > 1:
        threading.Thread(
            target=_download_remaining,
            args=(cache, tracks[1:]),
            daemon=True,
        ).start()

    if device_type == "sonos":
        m3u_content = pl.generate_m3u(tracks, hostname)
        _m3u_store[playlist_id] = m3u_content
        m3u_url = f"{hostname}/music/m3u/{playlist_id}.m3u"
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
        queue = chromecast.get_queue(slug, cc, cache)
        queue.load(tracks, shuffle=shuffle, repeat=repeat)

    return jsonify({
        "status": "playing",
        "trackCount": len(tracks),
    })
