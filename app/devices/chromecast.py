import logging
import random
import time

import pychromecast
from pychromecast.controllers.media import MediaStatusListener
from pychromecast.controllers.multizone import MultizoneController
from pychromecast.controllers.receiver import CastStatusListener

logger = logging.getLogger(__name__)

# Instance cache: (ip, port) -> Chromecast object
_instance_cache = {}
# Slug cache: slug -> (ip, port)
_slug_cache = {}
# Queue per slug
_queues = {}


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


def get_instance(ip, port):
    if (ip, port) not in _instance_cache:
        cc = pychromecast.get_chromecast_from_host((ip, port, None, None, None))
        cc.wait()
        _instance_cache[(ip, port)] = cc
        # Find slug for this device to pass to the listener
        slug = next((s for s, addr in _slug_cache.items() if addr == (ip, port)), None)
        if slug:
            listener = _DeviceListener(slug)
            cc.register_status_listener(listener)
            cc.media_controller.register_status_listener(listener)
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

    # Build merged list: newly discovered + previously seen devices not yet evicted
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
    # If a finished queue exists for this device, restart it from the beginning
    for slug, q in list(_queues.items()):
        if q.cc is cc and q.tracks and cc.media_controller.status.player_state == "IDLE":
            q._order_pos = -1
            q.current = -1
            q._build_play_order()
            q._advance_and_play()
            return {"status": "playing"}
    cc.media_controller.play()
    return {"status": "playing"}


def stop(cc):
    # Clear any active queue for this device
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
    # find queue for this cc by matching slug
    has_queue = False
    for _, q in _queues.items():
        if q.cc is cc:
            result["queue"] = q.get_queue_info()
            has_queue = True
            break
    # if no queue but media is playing, read metadata from media controller
    if not has_queue and status != "IDLE":
        media_meta = mc_status.media_metadata or {}
        images = media_meta.get("images", [])
        result["nowPlaying"] = {
            "title": mc_status.title or media_meta.get("title"),
            "thumbnail": images[0].get("url") if images else None,
            "contentId": mc_status.content_id,
        }
    return result


# --- Queue for sequential MP3 playback ---

class ChromecastQueue(MediaStatusListener):
    def __init__(self, cc, cache):
        self.cc = cc
        self.cache = cache
        self.tracks = []      # list of track dicts with videoId, title, artists, thumbnail, etc.
        self.current = -1
        self.shuffle = False
        self.repeat = "off"   # "off", "all", "one"
        self._play_order = []  # index order for shuffle
        self._order_pos = -1
        self._notification_url = None  # set during notification to suppress external-media detection
        cc.media_controller.register_status_listener(self)

    def load(self, tracks, shuffle=False, repeat="off"):
        """Set track list and start playing first track."""
        self.tracks = list(tracks)
        self.shuffle = shuffle
        self.repeat = repeat
        self._build_play_order()
        self._order_pos = -1
        self.current = -1
        self._advance_and_play()

    def _build_play_order(self):
        order = list(range(len(self.tracks)))
        if self.shuffle:
            random.shuffle(order)
        self._play_order = order

    def set_shuffle(self, enabled):
        self.shuffle = enabled
        # rebuild order, keeping current track
        current_track_idx = self._play_order[self._order_pos] if 0 <= self._order_pos < len(self._play_order) else None
        self._build_play_order()
        if current_track_idx is not None and current_track_idx in self._play_order:
            self._order_pos = self._play_order.index(current_track_idx)

    def set_repeat(self, mode):
        """mode: 'off', 'all', 'one'"""
        self.repeat = mode

    def _advance_and_play(self):
        self._order_pos += 1
        if self._order_pos >= len(self._play_order):
            if self.repeat == "all":
                self._build_play_order()
                self._order_pos = 0
            else:
                logger.info("Queue finished")
                return
        self.current = self._play_order[self._order_pos]
        self._play_current()

    def play_next(self):
        if self.repeat == "one":
            self._play_current()
        else:
            self._advance_and_play()

    def play_prev(self):
        if self._order_pos > 0:
            self._order_pos -= 1
            self.current = self._play_order[self._order_pos]
        self._play_current()

    def _play_current(self):
        if self.current >= len(self.tracks):
            logger.info("Queue finished")
            return
        track = self.tracks[self.current]
        vid = track["videoId"]
        url = self.cache.get_song_url(vid)
        title = track.get("title")
        artists = track.get("artists", [])
        thumb = track.get("thumbnail")

        metadata = {
            "metadataType": 3,  # MusicTrackMediaMetadata
            "title": title,
            "artist": ", ".join(artists) if artists else None,
            "albumName": track.get("album"),
            "images": [{"url": thumb}] if thumb else [],
        }

        logger.info("Queue playing track %d/%d: %s - %s (url: %s)", self.current + 1, len(self.tracks), ", ".join(artists), title, url)
        self.cc.media_controller.play_media(
            url,
            "audio/mpeg",
            title=title,
            thumb=thumb,
            metadata=metadata,
            stream_type="BUFFERED",
        )
        try:
            self.cc.media_controller.block_until_active(timeout=30)
        except Exception as e:
            logger.error("Failed to start playback for %s: %s", url, e)

    def get_current_track(self):
        """Return current track info dict or None."""
        if 0 <= self.current < len(self.tracks):
            return self.tracks[self.current]
        return None

    def play_track_at(self, index):
        """Jump to a specific track by its index in the original tracks list."""
        if not (0 <= index < len(self.tracks)):
            return
        self.current = index
        if index in self._play_order:
            self._order_pos = self._play_order.index(index)
        self._play_current()

    def get_queue_info(self):
        """Return queue state for API responses."""
        track = self.get_current_track()
        return {
            "currentIndex": self.current,
            "trackCount": len(self.tracks),
            "currentTrack": track,
            "tracks": self.tracks,
            "shuffle": self.shuffle,
            "repeat": self.repeat,
        }

    def _is_our_content(self, content_id):
        """Check if the content_id belongs to a track in our queue."""
        if not content_id or not self.tracks:
            return False
        for t in self.tracks:
            vid = t.get("videoId", "")
            if vid and vid in content_id:
                return True
        return False

    def clear(self):
        """Destroy the queue."""
        logger.info("Queue cleared")
        self.tracks = []
        self.current = -1
        self._play_order = []
        self._order_pos = -1
        # remove from global dict
        for slug, q in list(_queues.items()):
            if q is self:
                del _queues[slug]
                break

    def new_media_status(self, status):
        logger.info("Media status: state=%s idle_reason=%s content=%s",
                     status.player_state, status.idle_reason, status.content_id)

        # stopped by user or app quit
        if status.player_state == "IDLE" and status.idle_reason == "CANCELLED":
            logger.info("Playback cancelled, clearing queue")
            self.clear()
            return

        # different media took over (e.g. radio) — but ignore our own notification sound
        if (status.player_state in ("PLAYING", "BUFFERING")
                and status.content_id
                and self.tracks
                and not self._is_our_content(status.content_id)
                and status.content_id != self._notification_url):
            logger.info("External media detected (%s), clearing queue", status.content_id)
            self.clear()
            return

        if status.player_state == "IDLE" and status.idle_reason in ("FINISHED", "ERROR"):
            # Ignore IDLE events for the notification sound — _NotificationListener handles resume
            if self._notification_url and status.content_id == self._notification_url:
                return
            if status.idle_reason == "ERROR":
                logger.error("Playback error for track %d, skipping", self.current)
            self.play_next()

    def load_media_failed(self, queue_item_id, error_code):
        logger.error("Load media failed for track %d (error %s), skipping", self.current, error_code)
        self.play_next()


def get_queue(slug, cc=None, cache=None):
    """Get or create a queue for a Chromecast by slug."""
    if slug not in _queues:
        if cc is None or cache is None:
            return None
        _queues[slug] = ChromecastQueue(cc, cache)
    q = _queues[slug]
    if cc is not None:
        q.cc = cc
    if cache is not None:
        q.cache = cache
    return q


class _NotificationListener(MediaStatusListener):
    """Plays a notification sound then restores previous playback."""

    def __init__(self, cc, slug, resume_fn):
        self._cc = cc
        self._slug = slug
        self._resume_fn = resume_fn
        self._done = False
        cc.media_controller.register_status_listener(self)

    def _finish(self, resume=True):
        if self._done:
            return
        self._done = True
        try:
            self._cc.media_controller._status_listeners.remove(self)
        except ValueError:
            pass
        if resume:
            import threading
            t = threading.Thread(target=self._run_resume, daemon=True)
            t.start()

    def _run_resume(self):
        try:
            self._resume_fn()
        except Exception as e:
            logger.error("Notification resume failed for %s: %s", self._slug, e)

    def new_media_status(self, status):
        if self._done:
            return
        if status.player_state == "IDLE" and status.idle_reason in ("FINISHED", "ERROR", "CANCELLED"):
            self._finish()

    def load_media_failed(self, queue_item_id, error_code):
        self._finish()


def play_notification(cc, slug, sound_url, media_type="audio/mp3"):
    """Pause current playback, play notification sound, then restore."""
    mc = cc.media_controller
    mc_status = mc.status

    was_playing = mc_status.player_is_playing
    current_content_id = mc_status.content_id
    current_content_type = mc_status.content_type or "audio/mp3"
    current_position = mc_status.adjusted_current_time  # seconds, float

    # Capture queue state before interrupting
    queue = _queues.get(slug)
    current_track_index = queue.current if queue else None
    current_order_pos = queue._order_pos if queue else None

    if was_playing:
        mc.pause()

    # Tell the queue to ignore the notification URL so it doesn't self-destruct
    if queue:
        queue._notification_url = sound_url

    def _resume():
        if queue is not None and current_track_index is not None and 0 <= current_track_index < len(queue.tracks):
            # Restore queue in global dict in case it was cleared
            if slug not in _queues:
                _queues[slug] = queue
            queue._notification_url = None
            queue._order_pos = current_order_pos
            queue.current = current_track_index
            queue._play_current()  # already calls block_until_active internally
            if current_position and current_position > 0:
                logger.info("Seeking to %.1fs after notification resume", current_position)
                try:
                    time.sleep(0.5)
                    mc.seek(current_position)
                except Exception as e:
                    logger.warning("Seek after notification failed: %s", e)
        elif was_playing and current_content_id:
            # Treat as LIVE (radio) since there's no active queue
            mc.play_media(current_content_id, current_content_type, stream_type="LIVE")
            mc.block_until_active()
        # else was already paused — leave paused

    mc.play_media(sound_url, media_type, stream_type="BUFFERED")
    try:
        mc.block_until_active(timeout=15)
    except Exception as e:
        logger.error("Notification sound failed to start on %s: %s", slug, e)
        if queue:
            queue._notification_url = None
        _resume()
        return {"status": "notification_failed"}
    # Register listener after notification starts so pause IDLE events don't trigger resume
    _NotificationListener(cc, slug, _resume)
    return {"status": "notification_playing"}
