import logging
import threading
import time

import soco

logger = logging.getLogger(__name__)


# Instance cache: slug -> SoCo device object
_slug_cache = {}


def discover():
    devices = soco.discover()
    if not devices:
        return []
    return [
        {
            "type": "sonos",
            "friendly_name": d.player_name,
            "slug": d.player_name.lower().replace(" ", "_"),
            "host": d.ip_address,
            "port": 1400,
        }
        for d in devices
    ]


def get_by_slug(slug):
    return _slug_cache.get(slug)


_cached_devices = []


def update_cache():
    global _cached_devices
    raw = soco.discover() or []
    for d in raw:
        slug = d.player_name.lower().replace(" ", "_")
        _slug_cache[slug] = d
    _cached_devices = discover()


def get_cached_devices():
    return list(_cached_devices)


def play_media(device, url):
    device.play_uri(uri=url, force_radio=True)
    return {"status": "playing", "url": url}


def pause(device):
    device.pause()
    return {"status": "paused"}


def resume(device):
    device.play()
    return {"status": "playing"}


def stop(device):
    device.stop()
    return {"status": "stopped"}


def get_volume(device):
    return {"volume": device.volume / 100.0}


def set_volume(device, volume):
    device.volume = int(float(volume) * 100)
    return {"status": "volume set", "volume": device.volume / 100.0}


def adjust_volume(device, delta):
    device.set_relative_volume(int(float(delta) * 100))
    return {"status": "volume changed", "volume": device.volume / 100.0}


def next_track(device):
    device.next()
    return {"status": "next"}


def prev_track(device):
    device.previous()
    return {"status": "previous"}


def set_shuffle(device, enabled):
    mode = device.play_mode
    if enabled:
        device.play_mode = "SHUFFLE" if "REPEAT" not in mode else "SHUFFLE_REPEAT_ONE" if mode == "REPEAT_ONE" else "SHUFFLE"
    else:
        device.play_mode = "NORMAL" if "REPEAT" not in mode else "REPEAT_ONE" if "ONE" in mode else "REPEAT_ALL"
    return {"shuffle": enabled}


def set_repeat(device, mode):
    current = device.play_mode
    is_shuffle = "SHUFFLE" in current
    if mode == "all":
        device.play_mode = "SHUFFLE_REPEAT_ONE" if is_shuffle else "REPEAT_ALL"
    elif mode == "one":
        device.play_mode = "SHUFFLE_REPEAT_ONE" if is_shuffle else "REPEAT_ONE"
    else:
        device.play_mode = "SHUFFLE" if is_shuffle else "NORMAL"
    return {"repeat": mode}


def get_state(device):
    info = device.get_current_transport_info()
    transport = info.get("current_transport_state", "STOPPED")
    if transport == "PLAYING":
        status = "PLAYING"
    elif transport == "PAUSED_PLAYBACK":
        status = "PAUSED"
    else:
        status = "IDLE"
    return {"status": status, "volume": device.volume / 100.0}


def play_notification(device, sound_url):
    """Pause current playback, play notification sound, then restore."""
    info = device.get_current_transport_info()
    transport = info.get("current_transport_state", "STOPPED")
    was_playing = transport == "PLAYING"

    track_info = device.get_current_track_info()
    current_uri = track_info.get("uri")

    if was_playing:
        device.pause()

    def _play_and_restore():
        try:
            device.play_uri(uri=sound_url, force_radio=False)
            # Poll until notification finishes
            while True:
                time.sleep(1)
                state = device.get_current_transport_info().get("current_transport_state", "STOPPED")
                if state not in ("PLAYING", "BUFFERING_PLAYBACK"):
                    break
        except Exception as e:
            logger.error("Notification playback error on Sonos: %s", e)
        finally:
            if was_playing and current_uri:
                try:
                    device.play_uri(uri=current_uri, force_radio=True)
                except Exception as e:
                    logger.error("Sonos notification resume failed: %s", e)

    t = threading.Thread(target=_play_and_restore, daemon=True)
    t.start()
    return {"status": "notification_playing"}
