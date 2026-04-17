from ytmusicapi import YTMusic

_yt = YTMusic()


def search(query, filter_type="songs"):
    """Search YouTube Music.

    filter_type: "songs", "artists", "playlists", "albums"
    """
    results = _yt.search(query, filter=filter_type)
    if filter_type == "songs":
        return [
            {
                "videoId": r.get("videoId"),
                "title": r.get("title"),
                "artists": [a["name"] for a in r.get("artists", [])],
                "album": (r.get("album") or {}).get("name"),
                "duration": r.get("duration"),
                "thumbnail": _best_thumbnail(r.get("thumbnails", [])),
            }
            for r in results
            if r.get("videoId")
        ]
    elif filter_type == "artists":
        return [
            {
                "browseId": r.get("browseId"),
                "name": r.get("artist"),
                "thumbnail": _best_thumbnail(r.get("thumbnails", [])),
            }
            for r in results
            if r.get("browseId")
        ]
    elif filter_type == "playlists":
        return [
            {
                "playlistId": r.get("browseId"),
                "title": r.get("title"),
                "author": r.get("author"),
                "thumbnail": _best_thumbnail(r.get("thumbnails", [])),
                "trackCount": r.get("itemCount"),
            }
            for r in results
        ]
    elif filter_type == "albums":
        return [
            {
                "browseId": r.get("browseId"),
                "title": r.get("title"),
                "artists": [a["name"] for a in r.get("artists", [])],
                "year": r.get("year"),
                "thumbnail": _best_thumbnail(r.get("thumbnails", [])),
            }
            for r in results
            if r.get("browseId")
        ]
    return results


def get_artist(browse_id):
    artist = _yt.get_artist(browse_id)
    songs = []
    for s in (artist.get("songs") or {}).get("results", []):
        songs.append(
            {
                "videoId": s.get("videoId"),
                "title": s.get("title"),
                "album": (s.get("album") or {}).get("name"),
                "thumbnail": _best_thumbnail(s.get("thumbnails", [])),
            }
        )
    return {
        "name": artist.get("name"),
        "thumbnail": _best_thumbnail(artist.get("thumbnails", [])),
        "songs": songs,
    }


def get_playlist_tracks(playlist_id):
    playlist = _yt.get_playlist(playlist_id)
    tracks = []
    for t in playlist.get("tracks", []):
        tracks.append(
            {
                "videoId": t.get("videoId"),
                "title": t.get("title"),
                "artists": [a["name"] for a in t.get("artists", [])],
                "album": (t.get("album") or {}).get("name"),
                "duration": t.get("duration"),
                "thumbnail": _best_thumbnail(t.get("thumbnails", [])),
            }
        )
    return {
        "title": playlist.get("title"),
        "author": (playlist.get("author") or {}).get("name"),
        "thumbnail": _best_thumbnail(playlist.get("thumbnails", [])),
        "trackCount": playlist.get("trackCount"),
        "tracks": tracks,
    }


def get_album(browse_id):
    album = _yt.get_album(browse_id)
    tracks = []
    for t in album.get("tracks", []):
        tracks.append(
            {
                "videoId": t.get("videoId"),
                "title": t.get("title"),
                "artists": [a["name"] for a in t.get("artists", [])],
                "album": album.get("title"),
                "duration": t.get("duration"),
                "thumbnail": _best_thumbnail(t.get("thumbnails", [])),
            }
        )
    return {
        "title": album.get("title"),
        "artists": [a["name"] for a in album.get("artists", [])],
        "year": album.get("year"),
        "thumbnail": _best_thumbnail(album.get("thumbnails", [])),
        "trackCount": album.get("trackCount"),
        "audioPlaylistId": album.get("audioPlaylistId"),
        "tracks": tracks,
    }


def _best_thumbnail(thumbnails):
    if not thumbnails:
        return None
    return max(thumbnails, key=lambda t: t.get("width", 0)).get("url")
