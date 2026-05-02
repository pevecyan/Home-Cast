import logging
import threading
from datetime import datetime, timedelta

from flask import Blueprint, request, jsonify

from app.devices import chromecast, sonos
from app.devices.discovery import get_all_devices, refresh_cache
from app.ws import broadcast_states

logger = logging.getLogger(__name__)

# Sleep timers: "slug:type" -> { timer: Timer, ends_at: str (ISO) }
_sleep_timers = {}

# Volume locks: "slug:type" -> locked volume (0.0-1.0), or absent if not locked
_volume_locks: dict[str, float] = {}


def _stop_device_for_sleep(slug, device_type):
    """Called by sleep timer to stop the device."""
    logger.info("Sleep timer expired for %s:%s", slug, device_type)
    if device_type == "sonos":
        device = sonos.get_by_slug(slug)
        if device:
            sonos.stop(device)
    else:
        cc = chromecast.get_by_slug(slug)
        if cc:
            chromecast.stop(cc)
    _sleep_timers.pop(f"{slug}:{device_type}", None)


def get_sleep_timer(slug, device_type):
    """Return sleep timer info if active, else None."""
    key = f"{slug}:{device_type}"
    info = _sleep_timers.get(key)
    if info and info["timer"].is_alive():
        return {"endsAt": info["ends_at"]}
    _sleep_timers.pop(key, None)
    return None

devices_bp = Blueprint("devices", __name__)


def _get_device(slug, device_type):
    if device_type == "sonos":
        return sonos.get_by_slug(slug), "sonos"
    return chromecast.get_by_slug(slug), "chromecast"


def _device_action(device, device_type, action, **kwargs):
    module = sonos if device_type == "sonos" else chromecast
    fn = getattr(module, action)
    return fn(device, **kwargs)


# --- Device listing ---

@devices_bp.route("/get-devices", methods=["GET"])
def list_devices():
    return jsonify(get_all_devices())


@devices_bp.route("/refresh-devices", methods=["POST"])
def refresh_devices():
    devices = refresh_cache()
    return jsonify(devices)


# --- IP/Port endpoints (Chromecast only) ---

@devices_bp.route("/device/ip/play-url", methods=["POST"])
def play_url_by_ip():
    data = request.json
    cc = chromecast.get_instance(data.get("deviceIP"), data.get("devicePort"))
    result = chromecast.play_media(cc, data.get("url"), data.get("mediaType", "audio/mp3"))
    return jsonify(result)


@devices_bp.route("/device/ip/pause", methods=["POST"])
def pause_by_ip():
    data = request.json
    cc = chromecast.get_instance(data.get("deviceIP"), data.get("devicePort"))
    return jsonify(chromecast.pause(cc))


@devices_bp.route("/device/ip/stop", methods=["POST"])
def stop_by_ip():
    data = request.json
    cc = chromecast.get_instance(data.get("deviceIP"), data.get("devicePort"))
    return jsonify(chromecast.stop(cc))


@devices_bp.route("/device/ip/volume", methods=["POST"])
def volume_by_ip():
    data = request.json
    cc = chromecast.get_instance(data.get("deviceIP"), data.get("devicePort"))
    return jsonify(chromecast.get_volume(cc))


@devices_bp.route("/device/ip/volume/set", methods=["POST"])
def set_volume_by_ip():
    data = request.json
    cc = chromecast.get_instance(data.get("deviceIP"), data.get("devicePort"))
    return jsonify(chromecast.set_volume(cc, data.get("volume")))


@devices_bp.route("/device/ip/volume/delta", methods=["POST"])
def volume_delta_by_ip():
    data = request.json
    cc = chromecast.get_instance(data.get("deviceIP"), data.get("devicePort"))
    return jsonify(chromecast.adjust_volume(cc, data.get("delta")))


@devices_bp.route("/device/ip/state", methods=["POST"])
def state_by_ip():
    data = request.json
    cc = chromecast.get_instance(data.get("deviceIP"), data.get("devicePort"))
    if not cc:
        return jsonify({"error": "Invalid IP or Port"}), 400
    return jsonify(chromecast.get_state(cc))


# --- Slug endpoints (Chromecast + Sonos) ---

@devices_bp.route("/device/slug/play-url", methods=["POST"])
def play_url_by_slug():
    data = request.json
    device, dtype = _get_device(data.get("slug"), data.get("type", "chromecast"))
    if not device:
        return jsonify({"error": "Device not found"}), 400
    result = _device_action(
        device, dtype, "play_media",
        url=data.get("url"),
        **({"media_type": data.get("mediaType", "audio/mp3")} if dtype == "chromecast" else {}),
    )
    return jsonify(result)


@devices_bp.route("/device/slug/pause", methods=["POST"])
def pause_by_slug():
    data = request.json
    device, dtype = _get_device(data.get("slug"), data.get("type", "chromecast"))
    if not device:
        return jsonify({"error": "Device not found"}), 400
    result = _device_action(device, dtype, "pause")
    broadcast_states()
    return jsonify(result)


@devices_bp.route("/device/slug/resume", methods=["POST"])
def resume_by_slug():
    data = request.json
    device, dtype = _get_device(data.get("slug"), data.get("type", "chromecast"))
    if not device:
        return jsonify({"error": "Device not found"}), 400
    result = _device_action(device, dtype, "resume")
    broadcast_states()
    return jsonify(result)


@devices_bp.route("/device/slug/stop", methods=["POST"])
def stop_by_slug():
    data = request.json
    device, dtype = _get_device(data.get("slug"), data.get("type", "chromecast"))
    if not device:
        return jsonify({"error": "Device not found"}), 400
    result = _device_action(device, dtype, "stop")
    broadcast_states()
    return jsonify(result)


@devices_bp.route("/device/slug/volume", methods=["POST"])
def volume_by_slug():
    data = request.json
    device, dtype = _get_device(data.get("slug"), data.get("type", "chromecast"))
    if not device:
        return jsonify({"error": "Device not found"}), 400
    return jsonify(_device_action(device, dtype, "get_volume"))


@devices_bp.route("/device/slug/volume/set", methods=["POST"])
def set_volume_by_slug():
    data = request.json
    slug = data.get("slug")
    dtype = data.get("type", "chromecast")
    if f"{slug}:{dtype}" in _volume_locks:
        return jsonify({"error": "volume locked"}), 423
    device, dtype = _get_device(slug, dtype)
    if not device:
        return jsonify({"error": "Device not found"}), 400
    result = _device_action(device, dtype, "set_volume", volume=data.get("volume"))
    broadcast_states()
    return jsonify(result)


@devices_bp.route("/device/slug/volume/delta", methods=["POST"])
def volume_delta_by_slug():
    data = request.json
    slug = data.get("slug")
    dtype = data.get("type", "chromecast")
    if f"{slug}:{dtype}" in _volume_locks:
        return jsonify({"error": "volume locked"}), 423
    device, dtype = _get_device(slug, dtype)
    if not device:
        return jsonify({"error": "Device not found"}), 400
    return jsonify(_device_action(device, dtype, "adjust_volume", delta=data.get("delta")))


@devices_bp.route("/device/slug/volume/lock", methods=["POST"])
def lock_volume():
    data = request.json
    slug = data.get("slug")
    dtype = data.get("type", "chromecast")
    device, dtype = _get_device(slug, dtype)
    if not device:
        return jsonify({"error": "Device not found"}), 400
    # Snapshot current volume as the lock target
    state = _device_action(device, dtype, "get_volume")
    _volume_locks[f"{slug}:{dtype}"] = float(state["volume"])
    return jsonify({"locked": True, "volume": state["volume"]})


@devices_bp.route("/device/slug/volume/unlock", methods=["POST"])
def unlock_volume():
    data = request.json
    slug = data.get("slug")
    dtype = data.get("type", "chromecast")
    _volume_locks.pop(f"{slug}:{dtype}", None)
    return jsonify({"locked": False})


@devices_bp.route("/device/slug/next", methods=["POST"])
def next_by_slug():
    data = request.json
    slug = data.get("slug")
    device_type = data.get("type", "chromecast")
    if device_type == "sonos":
        device = sonos.get_by_slug(slug)
        if not device:
            return jsonify({"error": "Device not found"}), 400
        result = sonos.next_track(device)
        broadcast_states()
        return jsonify(result)
    else:
        queue = chromecast.get_queue(slug)
        if not queue:
            return jsonify({"error": "No active queue for this device"}), 400
        queue.play_next()
        broadcast_states()
        return jsonify({"status": "next"})


@devices_bp.route("/device/slug/prev", methods=["POST"])
def prev_by_slug():
    data = request.json
    slug = data.get("slug")
    device_type = data.get("type", "chromecast")
    if device_type == "sonos":
        device = sonos.get_by_slug(slug)
        if not device:
            return jsonify({"error": "Device not found"}), 400
        result = sonos.prev_track(device)
        broadcast_states()
        return jsonify(result)
    else:
        queue = chromecast.get_queue(slug)
        if not queue:
            return jsonify({"error": "No active queue for this device"}), 400
        queue.play_prev()
        broadcast_states()
        return jsonify({"status": "previous"})


@devices_bp.route("/device/slug/play-track", methods=["POST"])
def play_track_by_slug():
    data = request.json
    slug = data.get("slug")
    index = data.get("index")
    if index is None:
        return jsonify({"error": "index is required"}), 400
    queue = chromecast.get_queue(slug)
    if not queue:
        return jsonify({"error": "No active queue for this device"}), 400
    queue.play_track_at(int(index))
    broadcast_states()
    return jsonify({"status": "playing", "index": index})



@devices_bp.route("/device/slug/repeat", methods=["POST"])
def repeat_by_slug():
    data = request.json
    slug = data.get("slug")
    mode = data.get("mode", "off")
    device_type = data.get("type", "chromecast")
    if device_type == "sonos":
        device = sonos.get_by_slug(slug)
        if not device:
            return jsonify({"error": "Device not found"}), 400
        result = sonos.set_repeat(device, mode)
        broadcast_states()
        return jsonify(result)
    else:
        queue = chromecast.get_queue(slug)
        if not queue:
            return jsonify({"error": "No active queue for this device"}), 400
        queue.set_repeat(mode)
        broadcast_states()
        return jsonify({"repeat": queue.repeat})


@devices_bp.route("/device/slug/sleep", methods=["POST"])
def sleep_by_slug():
    data = request.json
    slug = data.get("slug")
    device_type = data.get("type", "chromecast")
    minutes = data.get("minutes", 0)
    key = f"{slug}:{device_type}"

    # cancel existing timer
    existing = _sleep_timers.pop(key, None)
    if existing and existing["timer"].is_alive():
        existing["timer"].cancel()

    if minutes <= 0:
        broadcast_states()
        return jsonify({"status": "cancelled"})

    ends_at = (datetime.now() + timedelta(minutes=minutes)).isoformat()
    timer = threading.Timer(minutes * 60, _stop_device_for_sleep, args=[slug, device_type])
    timer.daemon = True
    timer.start()
    _sleep_timers[key] = {"timer": timer, "ends_at": ends_at}

    broadcast_states()
    return jsonify({"sleepMinutes": minutes, "sleepEndsAt": ends_at})


@devices_bp.route("/device/slug/notify", methods=["POST"])
def notify_by_slug():
    data = request.json
    slug = data.get("slug")
    device_type = data.get("type", "chromecast")
    sound_url = data.get("soundUrl")
    if not sound_url:
        return jsonify({"error": "soundUrl is required"}), 400
    if device_type == "sonos":
        device = sonos.get_by_slug(slug)
        if not device:
            return jsonify({"error": "Device not found"}), 400
        result = sonos.play_notification(device, sound_url)
    else:
        cc = chromecast.get_by_slug(slug)
        if not cc:
            return jsonify({"error": "Device not found"}), 400
        media_type = data.get("mediaType", "audio/mp3")
        result = chromecast.play_notification(cc, slug, sound_url, media_type)
    broadcast_states()
    return jsonify(result)


@devices_bp.route("/device/slug/state", methods=["POST"])
def state_by_slug():
    data = request.json
    slug = data.get("slug")
    device_type = data.get("type", "chromecast")
    device, dtype = _get_device(slug, device_type)
    if not device:
        return jsonify({"error": "Device not found"}), 400
    result = _device_action(device, dtype, "get_state")
    sleep = get_sleep_timer(slug, device_type)
    if sleep:
        result["sleepTimer"] = sleep
    return jsonify(result)
