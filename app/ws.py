"""WebSocket support for real-time device state updates."""

import time
import logging
import threading

from flask_socketio import SocketIO, emit

from app.devices import chromecast, sonos
from app.devices.discovery import get_all_devices

logger = logging.getLogger(__name__)

socketio = SocketIO(cors_allowed_origins="*", async_mode="threading")

STATE_POLL_INTERVAL = 3  # seconds

# Last known states for diffing
_last_states = {}


def _get_device_state(device):
    """Get state for a single device, matching the REST endpoint logic."""
    from app.devices.routes import get_sleep_timer

    slug = device["slug"]
    dtype = device["type"]
    try:
        if dtype == "sonos":
            d = sonos.get_by_slug(slug)
            if not d:
                return None
            state = sonos.get_state(d)
        else:
            cc = chromecast.get_by_slug(slug)
            if not cc:
                return None
            state = chromecast.get_state(cc)
        sleep = get_sleep_timer(slug, dtype)
        if sleep:
            state["sleepTimer"] = sleep
        return state
    except Exception:
        logger.debug("Failed to get state for %s:%s", slug, dtype, exc_info=True)
        return None


def _poll_loop():
    """Background loop that polls device states and emits changes."""
    global _last_states
    while True:
        try:
            devices = get_all_devices()
            all_states = {}
            for device in devices:
                key = f"{device['slug']}:{device['type']}"
                state = _get_device_state(device)
                if state is not None:
                    all_states[key] = state

            # Emit only if something changed
            if all_states != _last_states:
                _last_states = all_states
                socketio.emit("states", all_states)
        except Exception:
            logger.debug("WS poll error", exc_info=True)

        time.sleep(STATE_POLL_INTERVAL)


def broadcast_states():
    """Force an immediate state broadcast (call after actions like play/stop/volume)."""
    global _last_states
    try:
        devices = get_all_devices()
        all_states = {}
        for device in devices:
            key = f"{device['slug']}:{device['type']}"
            state = _get_device_state(device)
            if state is not None:
                all_states[key] = state
        _last_states = all_states
        socketio.emit("states", all_states)
    except Exception:
        logger.debug("Broadcast error", exc_info=True)


@socketio.on("connect")
def on_connect():
    """Send current states on new client connection."""
    logger.info("WS client connected")
    devices = get_all_devices()
    all_states = {}
    for device in devices:
        key = f"{device['slug']}:{device['type']}"
        state = _get_device_state(device)
        if state is not None:
            all_states[key] = state
    emit("states", all_states)


def start_poll_thread():
    t = threading.Thread(target=_poll_loop, daemon=True)
    t.start()
