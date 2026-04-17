import time
import logging
import threading

from app.devices import chromecast, sonos

logger = logging.getLogger(__name__)

CACHE_UPDATE_INTERVAL = 600  # 10 minutes


def get_all_devices():
    """Return devices from cache (non-blocking)."""
    return chromecast.get_cached_devices() + sonos.get_cached_devices()


def refresh_cache():
    """Force refresh device cache (blocking)."""
    logger.info("Force refreshing device cache...")
    chromecast.update_cache()
    sonos.update_cache()
    return get_all_devices()


def _update_loop():
    while True:
        try:
            logger.info("Updating device cache...")
            chromecast.update_cache()
            sonos.update_cache()
        except Exception:
            logger.exception("Error updating device cache")
        time.sleep(CACHE_UPDATE_INTERVAL)


def start_cache_updater():
    t = threading.Thread(target=_update_loop, daemon=True)
    t.start()
