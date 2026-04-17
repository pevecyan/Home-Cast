import os
import time
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
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._start_cleanup_thread()

    def get_song_path(self, video_id):
        path = self.cache_dir / f"{video_id}.mp3"
        if path.exists():
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

    def cleanup_expired(self):
        if not self.cache_dir.exists():
            return
        now = time.time()
        for f in self.cache_dir.iterdir():
            if f.is_file() and (now - f.stat().st_mtime) > self.ttl:
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


def get_cache():
    if _cache is None:
        raise RuntimeError("SongCache not initialized -- call init_cache first")
    return _cache
