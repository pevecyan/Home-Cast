"""Tests for playlist cover art capture.

When a playlist is saved we fetch the first track's picture and store it as a
base64 data URI on the playlist (``cover``). For a custom playlist we fall back
to the first track that actually has a fetchable picture.
"""

import base64

import pytest

from app.music import playlist as pl


class FakeResponse:
    def __init__(self, content=b"", status=200, content_type="image/jpeg"):
        self.content = content
        self._status = status
        self.headers = {"Content-Type": content_type}

    def raise_for_status(self):
        if self._status >= 400:
            raise RuntimeError(f"HTTP {self._status}")


@pytest.fixture(autouse=True)
def temp_playlists_file(tmp_path, monkeypatch):
    """Isolate persistence to a temp file per test."""
    monkeypatch.setattr(pl, "PLAYLISTS_FILE", tmp_path / "playlists.json")


@pytest.fixture
def fake_get(monkeypatch):
    """Stub requests.get; records the URLs requested."""
    calls = []
    responses = {}

    def _get(url, timeout=None):
        calls.append(url)
        if url in responses:
            return responses[url]
        return FakeResponse(content=b"IMGDATA")

    monkeypatch.setattr(pl.requests, "get", _get)
    _get.calls = calls
    _get.responses = responses
    return _get


def test_cover_captured_from_first_track(fake_get):
    tracks = [
        {"videoId": "a", "title": "A", "thumbnail": "http://img/a.jpg"},
        {"videoId": "b", "title": "B", "thumbnail": "http://img/b.jpg"},
    ]
    result = pl.create_playlist("My List", tracks)

    expected = "data:image/jpeg;base64," + base64.b64encode(b"IMGDATA").decode()
    assert result["cover"] == expected
    # only the first track was fetched
    assert fake_get.calls == ["http://img/a.jpg"]


def test_custom_playlist_uses_first_track_with_a_picture(fake_get):
    """First tracks lack a thumbnail (common for artist-sourced songs); the
    cover falls back to the first track that has one."""
    tracks = [
        {"videoId": "a", "title": "A", "thumbnail": None},
        {"videoId": "b", "title": "B"},  # no thumbnail key at all
        {"videoId": "c", "title": "C", "thumbnail": "http://img/c.jpg"},
    ]
    result = pl.create_playlist("Custom", tracks)

    assert result["cover"].startswith("data:image/jpeg;base64,")
    assert fake_get.calls == ["http://img/c.jpg"]


def test_no_thumbnails_leaves_cover_none(fake_get):
    tracks = [
        {"videoId": "a", "title": "A", "thumbnail": None},
        {"videoId": "b", "title": "B"},
    ]
    result = pl.create_playlist("No Art", tracks)

    assert result["cover"] is None
    assert fake_get.calls == []


def test_content_type_preserved_in_data_uri(fake_get):
    fake_get.responses["http://img/a.png"] = FakeResponse(
        content=b"PNGDATA", content_type="image/png; charset=binary"
    )
    tracks = [{"videoId": "a", "title": "A", "thumbnail": "http://img/a.png"}]
    result = pl.create_playlist("PNG", tracks)

    assert result["cover"].startswith("data:image/png;base64,")


def test_fetch_error_falls_through_to_next_track(fake_get):
    fake_get.responses["http://img/a.jpg"] = FakeResponse(status=404)
    tracks = [
        {"videoId": "a", "title": "A", "thumbnail": "http://img/a.jpg"},
        {"videoId": "b", "title": "B", "thumbnail": "http://img/b.jpg"},
    ]
    result = pl.create_playlist("Fallback", tracks)

    assert result["cover"].startswith("data:image/jpeg;base64,")
    assert fake_get.calls == ["http://img/a.jpg", "http://img/b.jpg"]


def test_oversized_image_skipped(fake_get):
    big = b"x" * (pl._COVER_MAX_BYTES + 1)
    fake_get.responses["http://img/a.jpg"] = FakeResponse(content=big)
    tracks = [
        {"videoId": "a", "title": "A", "thumbnail": "http://img/a.jpg"},
        {"videoId": "b", "title": "B", "thumbnail": "http://img/b.jpg"},
    ]
    result = pl.create_playlist("Big", tracks)

    # oversized first image skipped, falls back to second
    assert result["cover"] == "data:image/jpeg;base64," + base64.b64encode(b"IMGDATA").decode()


def test_update_backfills_missing_cover(fake_get):
    created = pl.create_playlist("Empty", [])
    assert created["cover"] is None

    updated = pl.update_playlist(
        created["id"],
        tracks=[{"videoId": "a", "title": "A", "thumbnail": "http://img/a.jpg"}],
    )
    assert updated["cover"].startswith("data:image/jpeg;base64,")


def test_update_does_not_refetch_existing_cover(fake_get):
    created = pl.create_playlist(
        "Has Cover",
        [{"videoId": "a", "title": "A", "thumbnail": "http://img/a.jpg"}],
    )
    original_cover = created["cover"]
    fake_get.calls.clear()

    updated = pl.update_playlist(
        created["id"],
        tracks=[{"videoId": "b", "title": "B", "thumbnail": "http://img/b.jpg"}],
    )
    # cover already present -> not refetched, unchanged
    assert updated["cover"] == original_cover
    assert fake_get.calls == []


# --- Cover fallback applied to cast/queue tracks (player._with_fallback_cover) ---

def test_fallback_cover_fills_only_missing_thumbnails():
    from app.music.player import _with_fallback_cover

    tracks = [
        {"videoId": "a", "thumbnail": "http://img/a.jpg"},
        {"videoId": "b"},                      # no thumbnail -> gets the cover
        {"videoId": "c", "thumbnail": None},   # falsy -> gets the cover
    ]
    out = _with_fallback_cover(tracks, "data:image/jpeg;base64,COVER")

    assert out[0]["thumbnail"] == "http://img/a.jpg"   # own thumbnail preserved
    assert out[1]["thumbnail"] == "data:image/jpeg;base64,COVER"
    assert out[2]["thumbnail"] == "data:image/jpeg;base64,COVER"
    # original list not mutated
    assert "thumbnail" not in tracks[1]


def test_fallback_cover_noop_without_cover():
    from app.music.player import _with_fallback_cover

    tracks = [{"videoId": "a"}]
    assert _with_fallback_cover(tracks, None) is tracks
