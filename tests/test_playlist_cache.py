"""Tests for keeping saved-playlist songs cached indefinitely.

Songs referenced by a saved playlist are "pinned": the TTL-based cleanup must
never evict them, so a playlist starts playing immediately. When a playlist is
deleted or a track removed, the now-orphaned files are evicted so disk usage
doesn't grow without bound. Saving/updating a playlist also pre-warms its
tracks so the very first play is instant.
"""

import time

import pytest

from app.music.downloader import SongCache
from app.music import playlist as pl


def _make_cache(tmp_path, ttl=3600):
    return SongCache(cache_dir=tmp_path, ttl=ttl, hostname="http://localhost:5000")


def _touch(cache, video_id, age_seconds=0.0):
    """Create a fake cached mp3 with an optional age (seconds in the past)."""
    path = cache.cache_dir / f"{video_id}.mp3"
    path.write_bytes(b"AUDIO")
    if age_seconds:
        old = time.time() - age_seconds
        import os
        os.utime(path, (old, old))
    return path


# --- SongCache pinning ---

def test_pinned_song_survives_expiry_check(tmp_path):
    cache = _make_cache(tmp_path, ttl=60)
    _touch(cache, "keep", age_seconds=1000)  # well past TTL
    cache.set_pin_provider(lambda: {"keep"})

    # get_song_path returns the pinned file even though it's older than TTL
    assert cache.get_song_path("keep") is not None


def test_unpinned_song_expires(tmp_path):
    cache = _make_cache(tmp_path, ttl=60)
    path = _touch(cache, "gone", age_seconds=1000)
    cache.set_pin_provider(lambda: set())

    assert cache.get_song_path("gone") is None
    assert not path.exists()  # expired file removed on access


def test_cleanup_skips_pinned(tmp_path):
    cache = _make_cache(tmp_path, ttl=60)
    keep = _touch(cache, "keep", age_seconds=1000)
    drop = _touch(cache, "drop", age_seconds=1000)
    cache.set_pin_provider(lambda: {"keep"})

    cache.cleanup_expired()

    assert keep.exists()
    assert not drop.exists()


def test_evict_unpinned_removes_orphans_only(tmp_path):
    cache = _make_cache(tmp_path)
    keep = _touch(cache, "keep")
    orphan = _touch(cache, "orphan")
    cache.set_pin_provider(lambda: {"keep"})

    cache.evict_unpinned(["keep", "orphan"])

    assert keep.exists()      # still referenced -> kept
    assert not orphan.exists()  # no longer referenced -> evicted


def test_pin_provider_failure_is_safe(tmp_path):
    cache = _make_cache(tmp_path, ttl=60)
    _touch(cache, "x", age_seconds=1000)

    def boom():
        raise RuntimeError("db down")

    cache.set_pin_provider(boom)
    # Falls back to "nothing pinned" rather than crashing playback.
    assert cache.get_song_path("x") is None


def test_prewarm_downloads_only_missing(tmp_path, monkeypatch):
    cache = _make_cache(tmp_path)
    _touch(cache, "have")  # already cached
    downloaded = []

    def fake_download(vid):
        downloaded.append(vid)
        return _touch(cache, vid)

    monkeypatch.setattr(cache, "download_song", fake_download)

    cache.prewarm(["have", "need", None, ""])
    # prewarm spawns threads; give them a moment to run
    for _ in range(50):
        if "need" in downloaded:
            break
        time.sleep(0.01)

    assert downloaded == ["need"]


# --- playlist module wiring ---

@pytest.fixture(autouse=True)
def temp_playlists_file(tmp_path, monkeypatch):
    monkeypatch.setattr(pl, "PLAYLISTS_FILE", tmp_path / "playlists.json")
    # Playlists in these tests have no thumbnails, so cover fetching is a no-op.


def test_pinned_video_ids_spans_all_playlists(monkeypatch):
    monkeypatch.setattr(pl, "_prewarm", lambda tracks: None)
    pl.create_playlist("A", [{"videoId": "1"}, {"videoId": "2"}])
    pl.create_playlist("B", [{"videoId": "2"}, {"videoId": "3"}])

    assert pl.pinned_video_ids() == {"1", "2", "3"}


def test_create_prewarms_tracks(monkeypatch):
    warmed = []
    monkeypatch.setattr(pl, "_prewarm", lambda tracks: warmed.append(pl._track_ids(tracks)))

    pl.create_playlist("A", [{"videoId": "1"}, {"videoId": "2"}])

    assert warmed == [["1", "2"]]


def test_update_prewarms_new_and_evicts_removed(monkeypatch):
    warmed, evicted = [], []
    monkeypatch.setattr(pl, "_prewarm", lambda tracks: warmed.append(pl._track_ids(tracks)))
    monkeypatch.setattr(pl, "_evict", lambda ids: evicted.append(set(ids)))

    created = pl.create_playlist("A", [{"videoId": "1"}, {"videoId": "2"}])
    warmed.clear()

    pl.update_playlist(created["id"], tracks=[{"videoId": "2"}, {"videoId": "3"}])

    assert warmed == [["3"]]        # only the newly added track is warmed
    assert evicted == [{"1"}]       # removed track evicted


def test_delete_evicts_when_not_referenced_elsewhere(monkeypatch):
    monkeypatch.setattr(pl, "_prewarm", lambda tracks: None)
    evicted = []
    monkeypatch.setattr(pl, "_evict", lambda ids: evicted.append(set(ids)))

    a = pl.create_playlist("A", [{"videoId": "1"}, {"videoId": "2"}])
    pl.delete_playlist(a["id"])

    # delete passes all of the playlist's ids to _evict; evict_unpinned then
    # keeps any still referenced by another playlist.
    assert evicted == [{"1", "2"}]


def test_shared_track_survives_when_one_playlist_deleted(tmp_path, monkeypatch):
    """A track in two playlists must NOT be evicted when only one is deleted."""
    cache = _make_cache(tmp_path)
    monkeypatch.setattr("app.music.downloader.get_cache", lambda: cache)
    monkeypatch.setattr(pl, "_prewarm", lambda tracks: None)
    cache.set_pin_provider(pl.pinned_video_ids)

    shared = _touch(cache, "shared")
    only_a = _touch(cache, "onlyA")

    a = pl.create_playlist("A", [{"videoId": "shared"}, {"videoId": "onlyA"}])
    pl.create_playlist("B", [{"videoId": "shared"}])

    pl.delete_playlist(a["id"])  # B still references "shared"

    assert shared.exists()       # kept: still pinned by playlist B
    assert not only_a.exists()   # evicted: no longer referenced
