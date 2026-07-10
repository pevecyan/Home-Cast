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


def _resolve_targets(slug, device_type):
    """Return list of (slug, dtype) to act on. Expands slug=='all' via device cache."""
    if slug != "all":
        return [(slug, device_type or "chromecast")]
    devices = get_all_devices()
    if device_type and device_type != "all":
        devices = [d for d in devices if d["type"] == device_type]
    return [(d["slug"], d["type"]) for d in devices]


def _fan_out(slug, device_type, per_device):
    """Run per_device(target_slug, target_dtype) for the resolved target(s).

    Single slug: returns per_device's result directly (caller handles the
    response, back-compat). slug=='all': runs for every target, tolerating
    per-device failures, broadcasts once, and returns a Flask JSON response
    of the aggregated results. Callers detect the aggregate by checking for
    a Flask Response (has ``status_code``).
    """
    targets = _resolve_targets(slug, device_type)
    if slug != "all":
        s, t = targets[0]
        return per_device(s, t)
    results = []
    for s, t in targets:
        try:
            results.append({"slug": s, "type": t, "result": per_device(s, t), "ok": True})
        except Exception as e:  # one bad device must not abort the rest
            logger.exception("all-fanout failed for %s:%s", s, t)
            results.append({"slug": s, "type": t, "error": str(e), "ok": False})
    broadcast_states()
    return jsonify({"results": results})


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


def _simple_action(action):
    """Build a per-device callable that resolves the device and runs a no-arg action."""
    def act(slug, dtype):
        device, dtype = _get_device(slug, dtype)
        if not device:
            raise ValueError("Device not found")
        return _device_action(device, dtype, action)
    return act


def _respond(out):
    """Finalize a _fan_out result. Aggregate (Flask Response) is returned as-is;
    single-slug result is broadcast once and wrapped in jsonify."""
    if hasattr(out, "status_code"):
        return out
    broadcast_states()
    return jsonify(out)


@devices_bp.route("/device/slug/pause", methods=["POST"])
def pause_by_slug():
    data = request.json
    try:
        out = _fan_out(data.get("slug"), data.get("type"), _simple_action("pause"))
    except ValueError:
        return jsonify({"error": "Device not found"}), 400
    return _respond(out)


@devices_bp.route("/device/slug/resume", methods=["POST"])
def resume_by_slug():
    data = request.json
    try:
        out = _fan_out(data.get("slug"), data.get("type"), _simple_action("resume"))
    except ValueError:
        return jsonify({"error": "Device not found"}), 400
    return _respond(out)


@devices_bp.route("/device/slug/stop", methods=["POST"])
def stop_by_slug():
    data = request.json
    try:
        out = _fan_out(data.get("slug"), data.get("type"), _simple_action("stop"))
    except ValueError:
        return jsonify({"error": "Device not found"}), 400
    return _respond(out)


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
    # Single-slug: a locked device is a hard 423 (unchanged behavior).
    if slug != "all" and f"{slug}:{dtype}" in _volume_locks:
        return jsonify({"error": "volume locked"}), 423

    def act(s, t):
        # In an all-fanout, a locked device is skipped as an ok:false entry.
        if f"{s}:{t}" in _volume_locks:
            raise ValueError("volume locked")
        device, t = _get_device(s, t)
        if not device:
            raise ValueError("Device not found")
        return _device_action(device, t, "set_volume", volume=data.get("volume"))

    try:
        out = _fan_out(slug, data.get("type"), act)
    except ValueError:
        return jsonify({"error": "Device not found"}), 400
    return _respond(out)


@devices_bp.route("/device/slug/volume/delta", methods=["POST"])
def volume_delta_by_slug():
    data = request.json
    slug = data.get("slug")
    dtype = data.get("type", "chromecast")
    if slug != "all" and f"{slug}:{dtype}" in _volume_locks:
        return jsonify({"error": "volume locked"}), 423

    def act(s, t):
        if f"{s}:{t}" in _volume_locks:
            raise ValueError("volume locked")
        device, t = _get_device(s, t)
        if not device:
            raise ValueError("Device not found")
        return _device_action(device, t, "adjust_volume", delta=data.get("delta"))

    try:
        out = _fan_out(slug, data.get("type"), act)
    except ValueError:
        return jsonify({"error": "Device not found"}), 400
    return _respond(out)


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

    def act(slug, dtype):
        if dtype == "sonos":
            device = sonos.get_by_slug(slug)
            if not device:
                raise ValueError("Device not found")
            return sonos.next_track(device)
        queue = chromecast.get_queue(slug)
        if not queue:
            raise ValueError("No active queue for this device")
        queue.play_next()
        return {"status": "next"}

    try:
        out = _fan_out(data.get("slug"), data.get("type"), act)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    return _respond(out)


@devices_bp.route("/device/slug/prev", methods=["POST"])
def prev_by_slug():
    data = request.json

    def act(slug, dtype):
        if dtype == "sonos":
            device = sonos.get_by_slug(slug)
            if not device:
                raise ValueError("Device not found")
            return sonos.prev_track(device)
        queue = chromecast.get_queue(slug)
        if not queue:
            raise ValueError("No active queue for this device")
        queue.play_prev()
        return {"status": "previous"}

    try:
        out = _fan_out(data.get("slug"), data.get("type"), act)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    return _respond(out)


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
    mode = data.get("mode", "off")

    def act(slug, dtype):
        if dtype == "sonos":
            device = sonos.get_by_slug(slug)
            if not device:
                raise ValueError("Device not found")
            return sonos.set_repeat(device, mode)
        queue = chromecast.get_queue(slug)
        if not queue:
            raise ValueError("No active queue for this device")
        queue.set_repeat(mode)
        return {"repeat": queue.repeat}

    try:
        out = _fan_out(data.get("slug"), data.get("type"), act)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    return _respond(out)


@devices_bp.route("/device/slug/sleep", methods=["POST"])
def sleep_by_slug():
    data = request.json
    minutes = data.get("minutes", 0)
    # Shared end time so an all-fanout schedules every device to stop together.
    ends_at = (datetime.now() + timedelta(minutes=minutes)).isoformat() if minutes > 0 else None

    def act(slug, dtype):
        key = f"{slug}:{dtype}"
        # cancel existing timer
        existing = _sleep_timers.pop(key, None)
        if existing and existing["timer"].is_alive():
            existing["timer"].cancel()

        if minutes <= 0:
            return {"status": "cancelled"}

        timer = threading.Timer(minutes * 60, _stop_device_for_sleep, args=[slug, dtype])
        timer.daemon = True
        timer.start()
        _sleep_timers[key] = {"timer": timer, "ends_at": ends_at}
        return {"sleepMinutes": minutes, "sleepEndsAt": ends_at}

    out = _fan_out(data.get("slug"), data.get("type"), act)
    return _respond(out)


@devices_bp.route("/device/slug/notify", methods=["POST"])
def notify_by_slug():
    data = request.json
    sound_url = data.get("soundUrl")
    if not sound_url:
        return jsonify({"error": "soundUrl is required"}), 400
    media_type = data.get("mediaType", "audio/mp3")

    def act(slug, dtype):
        if dtype == "sonos":
            device = sonos.get_by_slug(slug)
            if not device:
                raise ValueError("Device not found")
            return sonos.play_notification(device, sound_url)
        cc = chromecast.get_by_slug(slug)
        if not cc:
            raise ValueError("Device not found")
        return chromecast.play_notification(cc, slug, sound_url, media_type)

    try:
        out = _fan_out(data.get("slug"), data.get("type"), act)
    except ValueError:
        return jsonify({"error": "Device not found"}), 400
    return _respond(out)


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
