import logging
import random
import time

import pychromecast
from pychromecast.controllers import BaseController
from pychromecast.controllers.media import MediaStatusListener
from pychromecast.controllers.multizone import MultizoneController
from pychromecast.controllers.receiver import CastStatusListener

logger = logging.getLogger(__name__)

CAST_NAMESPACE = 'urn:x-cast:io.1home.homecast'

# Instance cache: (ip, port) -> Chromecast object
_instance_cache = {}
# Slug cache: slug -> (ip, port)
_slug_cache = {}
# Queue per slug
_queues = {}
# Cast app ID (set once at startup from config)
_cast_app_id = None


def _get_group_members(host, port, uuid):
    """Return list of member UUIDs for a group Chromecast via a direct TCP connection."""
    cc = pychromecast.get_chromecast_from_host((host, port, uuid, None, None))
    cc.wait()
    mz = MultizoneController(cc.uuid)
    cc.register_handler(mz)
    mz.update_members()
    # wait up to 3 seconds for the multizone status response
    deadline = time.time() + 3
    while not mz.members and time.time() < deadline:
        time.sleep(0.1)
    members = mz.members
    cc.unregister_handler(mz)
    cc.disconnect()
    return members


def discover():
    chromecasts, browser = pychromecast.get_chromecasts()
    browser.stop_discovery()
    devices = []
    for cc in chromecasts:
        info = cc.cast_info
        device = {
            "type": "chromecast",
            "friendly_name": info.friendly_name,
            "slug": info.friendly_name.lower().replace(" ", "_"),
            "host": info.host,
            "port": info.port,
            "uuid": str(info.uuid),
            "cast_type": info.cast_type,  # "audio", "cast", "group"
        }
        if info.cast_type == "group":
            try:
                device["members"] = _get_group_members(info.host, info.port, info.uuid)
            except Exception:
                logger.exception("Failed to get members for group %s", info.friendly_name)
                device["members"] = []
        devices.append(device)
    return devices


class _DeviceListener(CastStatusListener, MediaStatusListener):
    """Listens to cast/media status events and enforces volume locks immediately."""

    def __init__(self, slug):
        self._slug = slug

    def new_cast_status(self, status):
        from app.devices.routes import _volume_locks
        from app.ws import broadcast_states
        key = f"{self._slug}:chromecast"
        if key not in _volume_locks:
            broadcast_states()
            return
        locked_vol = _volume_locks[key]
        if abs(status.volume_level - locked_vol) > 0.01:
            logger.info("Volume lock (event): restoring %s to %.2f (was %.2f)",
                        self._slug, locked_vol, status.volume_level)
            ip, port = _slug_cache.get(self._slug, (None, None))
            if ip:
                cc = _instance_cache.get((ip, port))
                if cc:
                    import threading
                    threading.Thread(target=cc.set_volume, args=(locked_vol,), daemon=True).start()
        broadcast_states()

    def new_media_status(self, status):
        from app.ws import broadcast_states
        broadcast_states()

    def load_media_failed(self, queue_item_id, error_code):
        pass


class HomeCastController(BaseController):
    """Receives custom messages from our receiver app and updates queue state."""

    def __init__(self, slug):
        super().__init__(CAST_NAMESPACE)
        self._slug = slug

    def channel_connected(self):
        self.send_message({"type": "GET_STATE"})

    def receive_message(self, _, data):
        if data.get("type") != "STATE":
            return False
        from app.ws import broadcast_states
        slug = self._slug
        if isinstance(_queues.get(slug), CustomReceiverQueue):
            return True
        queue_data = data.get("queue", [])
        current_item_id = data.get("currentItemId")
        repeat_mode = data.get("repeatMode", "OFF")
        repeat_map = {"REPEAT_OFF": "off", "REPEAT_ALL": "all", "REPEAT_SINGLE": "one"}
        repeat = repeat_map.get(repeat_mode, "off")
        tracks = []
        current_index = 0
        for i, item in enumerate(queue_data):
            meta = item.get("media", {}).get("metadata", {})
            images = meta.get("images", [])
            tracks.append({
                "videoId": item.get("media", {}).get("contentId", ""),
                "title": meta.get("title", ""),
                "artists": [meta.get("artist")] if meta.get("artist") else [],
                "album": meta.get("albumName"),
                "thumbnail": images[0].get("url") if images else None,
            })
            if item.get("itemId") == current_item_id:
                current_index = i
        ip, port = _slug_cache.get(slug, (None, None))
        cc = _instance_cache.get((ip, port)) if ip else None
        if cc and tracks:
            q = _make_restored_queue(cc, _cast_app_id, tracks, current_index, repeat)
            _queues[slug] = q
            logger.info("Restored queue for %s from receiver (%d tracks, index %d)", slug, len(tracks), current_index)
            broadcast_states()
        return True


def _make_restored_queue(cc, cast_app_id, tracks, current_index, repeat):
    """Create a fully functional CustomReceiverQueue from receiver state."""
    q = CustomReceiverQueue(cc, cache=None, cast_app_id=cast_app_id)
    q.tracks = tracks
    q._shuffled_tracks = tracks
    q.current = current_index
    q.repeat = repeat
    return q


def get_instance(ip, port):
    if (ip, port) not in _instance_cache:
        cc = pychromecast.get_chromecast_from_host((ip, port, None, None, None))
        cc.wait()
        _instance_cache[(ip, port)] = cc
        slug = next((s for s, addr in _slug_cache.items() if addr == (ip, port)), None)
        if slug:
            listener = _DeviceListener(slug)
            cc.register_status_listener(listener)
            cc.media_controller.register_status_listener(listener)
            controller = HomeCastController(slug)
            cc.register_handler(controller)
    return _instance_cache[(ip, port)]


def get_by_slug(slug):
    if slug not in _slug_cache:
        return None
    ip, port = _slug_cache[slug]
    return get_instance(ip, port)


_cached_devices = []
# slug -> last-seen timestamp (epoch seconds)
_last_seen = {}
DEVICE_EVICT_AFTER = 3600  # 1 hour


def update_cache():
    global _cached_devices
    now = time.time()
    devices = discover()
    for d in devices:
        ip, port = d["host"], d["port"]
        _slug_cache[d["slug"]] = (ip, port)
        _instance_cache[(ip, port)] = get_instance(ip, port)
        _last_seen[d["slug"]] = now

    seen_slugs = {d["slug"] for d in devices}
    retained = [
        d for d in _cached_devices
        if d["slug"] not in seen_slugs
        and now - _last_seen.get(d["slug"], 0) < DEVICE_EVICT_AFTER
    ]
    if retained:
        logger.info(
            "Retaining %d device(s) not seen in this scan: %s",
            len(retained),
            [d["slug"] for d in retained],
        )
    evicted = [
        d["slug"] for d in _cached_devices
        if d["slug"] not in seen_slugs
        and now - _last_seen.get(d["slug"], 0) >= DEVICE_EVICT_AFTER
    ]
    if evicted:
        logger.info("Evicting device(s) absent for >1 hour: %s", evicted)

    _cached_devices = devices + retained


def get_cached_devices():
    return list(_cached_devices)


def play_media(cc, url, media_type="audio/mp3"):
    mc = cc.media_controller
    mc.play_media(url, media_type)
    mc.block_until_active()
    return {"status": "playing", "url": url}


def pause(cc):
    cc.media_controller.pause()
    return {"status": "paused"}


def resume(cc):
    # If a finished queue exists, reload it via the custom receiver
    for slug, q in list(_queues.items()):
        if q.cc is cc and q.tracks and cc.media_controller.status.player_state == "IDLE":
            q._load_to_receiver(start_index=0)
            return {"status": "playing"}
    cc.media_controller.play()
    return {"status": "playing"}


def stop(cc):
    for slug, q in list(_queues.items()):
        if q.cc is cc:
            q.clear()
            break
    cc.quit_app()
    return {"status": "stopped"}


def get_volume(cc):
    return {"volume": cc.status.volume_level}


def set_volume(cc, volume):
    cc.set_volume(float(volume))
    return {"status": "volume set", "volume": cc.status.volume_level}


def adjust_volume(cc, delta):
    new_volume = max(0.0, min(1.0, cc.status.volume_level + float(delta)))
    cc.set_volume(new_volume)
    return {"status": "volume changed", "volume": cc.status.volume_level}


def get_state(cc):
    mc_status = cc.media_controller.status
    if mc_status.player_is_paused:
        status = "PAUSED"
    elif mc_status.player_is_playing:
        status = "PLAYING"
    else:
        status = "IDLE"
    volume = cc.status.volume_level
    result = {"status": status, "volume": volume}
    has_queue = False
    for _, q in _queues.items():
        if q.cc is cc:
            result["queue"] = q.get_queue_info()
            has_queue = True
            break
    if not has_queue and status != "IDLE":
        media_meta = mc_status.media_metadata or {}
        images = media_meta.get("images", [])
        result["nowPlaying"] = {
            "title": mc_status.title or media_meta.get("title"),
            "thumbnail": images[0].get("url") if images else None,
            "contentId": mc_status.content_id,
        }
    return result


def _send_custom_message(cc, message):
    """Send a message on the home-cast namespace to the running custom receiver."""
    try:
        cc.socket_client.send_app_message(CAST_NAMESPACE, message)
    except Exception as e:
        logger.warning("Failed to send custom message %s: %s", message.get("type"), e)


# --- Queue for custom receiver ---

class CustomReceiverQueue(MediaStatusListener):
    def __init__(self, cc, cache, cast_app_id):
        self.cc = cc
        self.cache = cache
        self.cast_app_id = cast_app_id
        self.tracks = []
        self.current = 0       # index into self.tracks (original order)
        self.repeat = "off"
        self._shuffled_tracks = []  # tracks in current play order
        self._reloading = False    # suppress clear() during intentional queue reload
        cc.media_controller.register_status_listener(self)

    def load(self, tracks, shuffle=False, repeat="off"):
        self.tracks = list(tracks)
        self.repeat = repeat
        self._shuffled_tracks = list(tracks)
        if shuffle:
            random.shuffle(self._shuffled_tracks)
        self.current = 0

        self._reloading = True
        self._load_to_receiver(start_index=0)

    def set_repeat(self, mode):
        self.repeat = mode
        _send_custom_message(self.cc, {"type": "SET_REPEAT", "mode": mode})

    def play_next(self):
        self.cc.media_controller.queue_next()

    def play_prev(self):
        self.cc.media_controller.queue_prev()

    def play_track_at(self, index):
        """Jump to a track by its index in the current play order."""
        if not (0 <= index < len(self._shuffled_tracks)):
            return
        self.current = index
        self._reloading = True
        self._load_to_receiver(start_index=index)

    def get_current_track(self):
        return self._current_track_dict()

    def get_queue_info(self):
        track = self.get_current_track()
        return {
            "currentIndex": self.current,
            "trackCount": len(self._shuffled_tracks),
            "currentTrack": track,
            "tracks": self._shuffled_tracks,
            "repeat": self.repeat,
        }

    def clear(self):
        logger.info("Queue cleared")
        self.tracks = []
        self._shuffled_tracks = []
        self.current = 0

        for slug, q in list(_queues.items()):
            if q is self:
                del _queues[slug]
                break

    # --- Internal ---

    def _current_track_dict(self):
        if 0 <= self.current < len(self._shuffled_tracks):
            return self._shuffled_tracks[self.current]
        if self.tracks:
            return self.tracks[0]
        return None

    def _repeat_mode_str(self):
        return {"off": "OFF", "all": "ALL", "one": "SINGLE"}.get(self.repeat, "OFF")

    def _load_to_receiver(self, start_index=0):
        """Launch the custom receiver app and load the full queue via queue_load."""
        import threading

        def _do_load():
            try:
                self._launch_and_load(start_index)
            except Exception as e:
                logger.error("Failed to load queue to receiver: %s", e)
            finally:
                self._reloading = False

        threading.Thread(target=_do_load, daemon=True).start()

    def _launch_and_load(self, start_index=0):
        current_app_id = self.cc.status.app_id if self.cc.status else None
        receiver_already_running = (
            self.cast_app_id and current_app_id == self.cast_app_id
        ) or (
            not self.cast_app_id and current_app_id is not None
        )
        if not receiver_already_running and self.cast_app_id:
            logger.info("Launching custom receiver app %s", self.cast_app_id)
            try:
                self.cc.start_app(self.cast_app_id, timeout=30)
                logger.info("Custom receiver %s launched successfully", self.cast_app_id)
            except Exception as e:
                logger.error("Could not launch custom receiver %s: %s", self.cast_app_id, e)
                return
            deadline = time.time() + 15
            while time.time() < deadline:
                time.sleep(0.3)
                app_id = self.cc.status.app_id if self.cc.status else None
                logger.debug("Waiting for receiver app — current app_id: %s", app_id)
                if app_id == self.cast_app_id:
                    logger.info("Custom receiver ready")
                    break

        tracks = self._shuffled_tracks
        if not tracks:
            return

        if receiver_already_running:
            logger.info("Receiver already running, sending RELOAD_QUEUE (start=%d)", start_index)
            items = []
            for track in tracks:
                url = self.cache.get_song_url(track["videoId"]) if self.cache else track["videoId"]
                items.append({
                    "url": url,
                    "mediaType": "audio/mpeg",
                    "metadata": self._build_metadata(track),
                })
            _send_custom_message(self.cc, {
                "type": "RELOAD_QUEUE",
                "items": items,
                "startIndex": start_index,
            })
            return

        logger.info("Loading queue of %d tracks to custom receiver (start=%d)", len(tracks), start_index)
        items = []
        for track in tracks:
            url = self.cache.get_song_url(track["videoId"]) if self.cache else track["videoId"]
            items.append({
                "url": url,
                "mediaType": "audio/mpeg",
                "metadata": self._build_metadata(track),
            })
        _send_custom_message(self.cc, {
            "type": "RELOAD_QUEUE",
            "items": items,
            "startIndex": start_index,
            "repeatMode": self._repeat_mode_str(),
        })

    def _build_metadata(self, track):
        artists = track.get("artists", [])
        thumb = track.get("thumbnail")
        return {
            "metadataType": 3,  # MusicTrackMediaMetadata
            "title": track.get("title"),
            "artist": ", ".join(artists) if artists else None,
            "albumName": track.get("album"),
            "images": [{"url": thumb}] if thumb else [],
        }

    def _is_our_content(self, content_id):
        if not content_id or not self.tracks:
            return False
        for t in self.tracks:
            vid = t.get("videoId", "")
            if vid and vid in content_id:
                return True
        return False

    def new_media_status(self, status):
        logger.debug("Media status: state=%s idle_reason=%s content=%s",
                     status.player_state, status.idle_reason, status.content_id)

        # Update current index based on content_id
        if status.player_state in ("PLAYING", "BUFFERING") and status.content_id:
            for idx, track in enumerate(self._shuffled_tracks):
                vid = track.get("videoId", "")
                if vid and vid in status.content_id:
                    if self.current != idx:
                        self.current = idx
                    break

        # Stopped by user or app quit (but not when we're intentionally reloading)
        if status.player_state == "IDLE" and status.idle_reason == "CANCELLED":
            if self._reloading:
                return
            logger.info("Playback cancelled, clearing queue")
            self.clear()
            return

        # External media took over
        if (status.player_state in ("PLAYING", "BUFFERING")
                and status.content_id
                and self.tracks
                and not self._is_our_content(status.content_id)):
            logger.info("External media detected (%s), clearing queue", status.content_id)
            self.clear()
            return

    def load_media_failed(self, queue_item_id, error_code):
        logger.error("Load media failed (error %s), skipping", error_code)
        self.play_next()


def get_queue(slug, cc=None, cache=None, cast_app_id=None):
    """Get or create a queue for a Chromecast by slug."""
    global _cast_app_id
    if cast_app_id is not None:
        _cast_app_id = cast_app_id
    if slug not in _queues:
        if cc is None or cache is None:
            return None
        _queues[slug] = CustomReceiverQueue(cc, cache, cast_app_id)
    q = _queues[slug]
    if cc is not None:
        q.cc = cc
    if cache is not None:
        q.cache = cache
    if cast_app_id is not None:
        q.cast_app_id = cast_app_id
    return q


def play_notification(cc, slug, sound_url, media_type="audio/mp3"):
    """Send notification to custom receiver — it handles pause/play/resume."""
    _send_custom_message(cc, {
        "type": "NOTIFICATION",
        "url": sound_url,
        "mediaType": media_type,
    })
    return {"status": "notification_playing"}
