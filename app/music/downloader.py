import os
import time
import queue
import logging
import threading
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)


class SongCache:
    def __init__(self, cache_dir, ttl, hostname):
        self.cache_dir = Path(cache_dir)
        self.ttl = ttl
        self.hostname = hostname.rstrip("/")
        self._downloads_in_progress = {}  # videoId -> threading.Event
        self._lock = threading.Lock()
        # Serialized background prewarm: a single worker drains this queue so
        # warming many saved playlists never spawns concurrent transcodes.
        self._prewarm_queue = queue.Queue()
        self._prewarm_queued = set()
        self._prewarm_worker = None
        self._prewarm_lock = threading.Lock()
        # Callable returning the set of videoIds that must never expire
        # (e.g. songs belonging to a saved playlist). Set via set_pin_provider.
        self._pin_provider = None
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._start_cleanup_thread()

    def set_pin_provider(self, provider):
        """Register a callable returning an iterable of pinned videoIds.

        Pinned songs are kept in the cache indefinitely, ignoring the TTL, so
        that saved playlists start playing immediately.
        """
        self._pin_provider = provider

    def _pinned_ids(self):
        if self._pin_provider is None:
            return set()
        try:
            return set(self._pin_provider())
        except Exception:
            logger.exception("Pin provider failed; treating nothing as pinned")
            return set()

    def get_song_path(self, video_id):
        path = self.cache_dir / f"{video_id}.mp3"
        if path.exists():
            if video_id in self._pinned_ids():
                return path
            age = time.time() - path.stat().st_mtime
            if age < self.ttl:
                return path
            # expired -- remove it
            path.unlink(missing_ok=True)
        return None

    def download_song(self, video_id):
        output_template = str(self.cache_dir / f"{video_id}.%(ext)s")
        url = f"https://music.youtube.com/watch?v={video_id}"
        cmd = [
            "yt-dlp",
            "-x",
            "--audio-format", "mp3",
            "-o", output_template,
            "--no-playlist",
            "--remote-components", "ejs:github",
            url,
        ]
        logger.info("Downloading %s ...", video_id)
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if result.returncode != 0:
            logger.error("yt-dlp failed for %s: %s", video_id, result.stderr)
            raise RuntimeError(f"yt-dlp failed: {result.stderr[:200]}")

        path = self.cache_dir / f"{video_id}.mp3"
        if not path.exists():
            raise RuntimeError(f"Downloaded file not found at {path}")
        logger.info("Downloaded %s -> %s", video_id, path)
        return path

    def ensure_song(self, video_id):
        """Return path to cached song, downloading if needed.
        Deduplicates concurrent requests for the same song.
        """
        cached = self.get_song_path(video_id)
        if cached:
            return cached

        with self._lock:
            # double-check after acquiring lock
            cached = self.get_song_path(video_id)
            if cached:
                return cached

            if video_id in self._downloads_in_progress:
                event = self._downloads_in_progress[video_id]
            else:
                event = threading.Event()
                self._downloads_in_progress[video_id] = event
                event = None  # signal that we are the downloader

        if event is not None:
            # another thread is downloading -- wait for it
            event.wait(timeout=150)
            path = self.get_song_path(video_id)
            if path:
                return path
            raise RuntimeError(f"Download of {video_id} failed (waited on other thread)")

        # we are the downloader
        try:
            path = self.download_song(video_id)
            return path
        finally:
            with self._lock:
                ev = self._downloads_in_progress.pop(video_id, None)
                if ev:
                    ev.set()

    def get_song_url(self, video_id):
        return f"{self.hostname}/media/{video_id}.mp3"

    def evict_unpinned(self, video_ids):
        """Immediately remove cached files for the given videoIds if they are
        no longer pinned by any playlist. Called when a playlist is deleted or
        edited so orphaned tracks don't linger forever.
        """
        pinned = self._pinned_ids()
        for vid in set(video_ids or []):
            if not vid or vid in pinned:
                continue
            path = self.cache_dir / f"{vid}.mp3"
            if path.exists():
                logger.info("Evicting orphaned cache file: %s.mp3", vid)
                path.unlink(missing_ok=True)

    def prewarm(self, video_ids):
        """Queue the given songs for background download if not already cached.

        Used to pre-fetch a saved playlist's tracks so the first play is
        instant. Downloads run through a single serialized worker (one
        yt-dlp/ffmpeg at a time) so warming many saved playlists at startup
        can't spawn dozens of concurrent transcodes and exhaust host memory.
        Failures are logged and ignored -- they'll be retried lazily on actual
        playback.
        """
        for vid in video_ids or []:
            if not vid or self.get_song_path(vid):
                continue
            with self._prewarm_lock:
                if vid in self._prewarm_queued:
                    continue
                self._prewarm_queued.add(vid)
                self._prewarm_queue.put(vid)
                self._ensure_prewarm_worker()

    def _ensure_prewarm_worker(self):
        """Start the single prewarm worker thread if it isn't already running.
        Must be called while holding self._prewarm_lock."""
        if self._prewarm_worker and self._prewarm_worker.is_alive():
            return

        def worker():
            while True:
                try:
                    vid = self._prewarm_queue.get(timeout=5)
                except queue.Empty:
                    # Idle: let the thread exit; it'll be recreated on demand.
                    with self._prewarm_lock:
                        if self._prewarm_queue.empty():
                            self._prewarm_worker = None
                            return
                    continue
                try:
                    self.ensure_song(vid)
                except Exception as e:
                    logger.warning("Prewarm of %s failed: %s", vid, e)
                finally:
                    with self._prewarm_lock:
                        self._prewarm_queued.discard(vid)
                    self._prewarm_queue.task_done()

        self._prewarm_worker = threading.Thread(target=worker, daemon=True)
        self._prewarm_worker.start()

    def cleanup_expired(self):
        if not self.cache_dir.exists():
            return
        now = time.time()
        pinned = self._pinned_ids()
        for f in self.cache_dir.iterdir():
            if not f.is_file():
                continue
            if f.stem in pinned:
                continue
            if (now - f.stat().st_mtime) > self.ttl:
                logger.info("Removing expired cache file: %s", f.name)
                f.unlink(missing_ok=True)

    def _start_cleanup_thread(self):
        def loop():
            while True:
                time.sleep(self.ttl / 2)
                try:
                    self.cleanup_expired()
                except Exception:
                    logger.exception("Cache cleanup error")

        t = threading.Thread(target=loop, daemon=True)
        t.start()


# Module-level singleton, initialized by create_app
_cache = None


def init_cache(config):
    global _cache
    _cache = SongCache(
        cache_dir=config["cache"]["dir"],
        ttl=config["cache"]["ttl"],
        hostname=config["hostname"],
    )
    # Pin songs belonging to saved playlists so they never expire, and
    # pre-warm them so playlists start playing immediately.
    from app.music.playlist import pinned_video_ids
    _cache.set_pin_provider(pinned_video_ids)
    _cache.prewarm(pinned_video_ids())


def get_cache():
    if _cache is None:
        raise RuntimeError("SongCache not initialized -- call init_cache first")
    return _cache
