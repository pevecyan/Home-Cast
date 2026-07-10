from ytmusicapi import YTMusic
from ytmusicapi.navigation import SINGLE_COLUMN_TAB, SECTION_LIST, nav

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


def _normalize_home_item(item):
    """Normalize a single item from a get_home() row into a card the UI can
    render and act on. Home rows mix albums/singles, playlists, songs/videos
    and artists; we tag each with a `kind` so the frontend knows what to do
    when it's clicked.
    """
    thumb = _best_thumbnail(item.get("thumbnails", []))
    artists = [a["name"] for a in item.get("artists", []) if a.get("name")]

    # Playlist card
    if item.get("playlistId"):
        return {
            "kind": "playlist",
            "playlistId": item.get("playlistId"),
            "title": item.get("title"),
            "subtitle": item.get("description") or ", ".join(artists),
            "thumbnail": thumb,
        }
    # Song / video card
    if item.get("videoId"):
        return {
            "kind": "song",
            "videoId": item.get("videoId"),
            "title": item.get("title"),
            "artists": artists,
            "subtitle": ", ".join(artists),
            "thumbnail": thumb,
        }
    # Album / single card (has a browseId + audioPlaylistId)
    if item.get("browseId") and item.get("audioPlaylistId"):
        return {
            "kind": "album",
            "browseId": item.get("browseId"),
            "title": item.get("title"),
            "subtitle": ", ".join(artists) or item.get("type"),
            "thumbnail": thumb,
        }
    # Artist card (browseId only)
    if item.get("browseId"):
        return {
            "kind": "artist",
            "browseId": item.get("browseId"),
            "title": item.get("title"),
            "subtitle": "Artist",
            "thumbnail": thumb,
        }
    return None


def get_home(limit=4):
    """Return the YouTube Music home feed as normalized card rows.

    Shape: [{ "title": str, "items": [normalized card, ...] }, ...]
    """
    rows = []
    for row in _yt.get_home(limit=limit):
        items = [
            card
            for card in (_normalize_home_item(i) for i in row.get("contents", []))
            if card
        ]
        if items:
            rows.append({"title": row.get("title"), "items": items})
    return rows


def get_mood_categories():
    """Return mood/genre chips grouped by section.

    Shape: [{ "title": str, "chips": [{ "title": str, "params": str }, ...] }]
    """
    groups = _yt.get_mood_categories()
    return [
        {
            "title": section,
            "chips": [
                {"title": c.get("title"), "params": c.get("params")}
                for c in chips
                if c.get("params")
            ],
        }
        for section, chips in groups.items()
    ]


def _runs_text(node):
    """Join the text runs of a title/subtitle node."""
    if not node:
        return None
    runs = node.get("runs") or []
    return "".join(r.get("text", "") for r in runs) or None


def _parse_two_row_card(item):
    """Parse a musicTwoRowItemRenderer (playlist/album/artist card)."""
    thumb = _best_thumbnail(
        nav(item, ["thumbnailRenderer", "musicThumbnailRenderer", "thumbnail", "thumbnails"], True) or []
    )
    title = _runs_text(item.get("title"))
    subtitle = _runs_text(item.get("subtitle"))
    endpoint = item.get("navigationEndpoint") or {}
    browse = (endpoint.get("browseEndpoint") or {})
    browse_id = browse.get("browseId")
    page_type = nav(
        browse,
        ["browseEndpointContextSupportedConfigs", "browseEndpointContextMusicConfig", "pageType"],
        True,
    )

    # Playlist browseIds are prefixed with "VL"; the playlistId strips it.
    if browse_id and (page_type == "MUSIC_PAGE_TYPE_PLAYLIST" or browse_id.startswith("VL")):
        return {
            "kind": "playlist",
            "playlistId": browse_id[2:] if browse_id.startswith("VL") else browse_id,
            "title": title,
            "subtitle": subtitle,
            "thumbnail": thumb,
        }
    if page_type == "MUSIC_PAGE_TYPE_ARTIST":
        return {"kind": "artist", "browseId": browse_id, "title": title, "subtitle": subtitle or "Artist", "thumbnail": thumb}
    if browse_id:
        return {"kind": "album", "browseId": browse_id, "title": title, "subtitle": subtitle, "thumbnail": thumb}
    return None


def _parse_responsive_song(item):
    """Parse a musicResponsiveListItemRenderer (individual song/video row)."""
    video_id = nav(item, ["playlistItemData", "videoId"], True) or nav(
        item, ["flexColumns", 0, "musicResponsiveListItemFlexColumnRenderer", "text", "runs", 0,
                "navigationEndpoint", "watchEndpoint", "videoId"], True
    )
    if not video_id:
        return None
    title = _runs_text(nav(item, ["flexColumns", 0, "musicResponsiveListItemFlexColumnRenderer", "text"], True))
    subtitle = _runs_text(nav(item, ["flexColumns", 1, "musicResponsiveListItemFlexColumnRenderer", "text"], True))
    thumb = _best_thumbnail(nav(item, ["thumbnail", "musicThumbnailRenderer", "thumbnail", "thumbnails"], True) or [])
    return {
        "kind": "song",
        "videoId": video_id,
        "title": title,
        "artists": [subtitle] if subtitle else [],
        "subtitle": subtitle,
        "thumbnail": thumb,
    }


def get_mood_playlists(params, limit=60):
    """Return the playlists/songs for a given mood/genre chip as normalized cards.

    We browse the mood page directly instead of using ytmusicapi's
    get_mood_playlists(), which crashes (KeyError: 'musicTwoRowItemRenderer')
    on moods whose sections mix song rows with playlist cards. Here we parse
    each item by its renderer type and skip anything unrecognized.
    """
    response = _yt._send_request(
        "browse", {"browseId": "FEmusic_moods_and_genres_category", "params": params}
    )
    cards = []
    for section in nav(response, SINGLE_COLUMN_TAB + SECTION_LIST):
        if "gridRenderer" in section:
            items = nav(section, ["gridRenderer", "items"], True) or []
        elif "musicCarouselShelfRenderer" in section:
            items = nav(section, ["musicCarouselShelfRenderer", "contents"], True) or []
        elif "musicImmersiveCarouselShelfRenderer" in section:
            items = nav(section, ["musicImmersiveCarouselShelfRenderer", "contents"], True) or []
        else:
            continue

        for wrapper in items:
            try:
                if "musicTwoRowItemRenderer" in wrapper:
                    card = _parse_two_row_card(wrapper["musicTwoRowItemRenderer"])
                elif "musicResponsiveListItemRenderer" in wrapper:
                    card = _parse_responsive_song(wrapper["musicResponsiveListItemRenderer"])
                else:
                    continue
            except Exception:
                continue
            if card and card.get("title"):
                cards.append(card)

    return cards[:limit]


def _best_thumbnail(thumbnails):
    if not thumbnails:
        return None
    return max(thumbnails, key=lambda t: t.get("width", 0)).get("url")
