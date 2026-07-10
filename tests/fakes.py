"""Fake in-memory devices standing in for real Chromecast/Sonos hardware.

These fakes are driven by the *real* ``app.devices.chromecast`` /
``app.devices.sonos`` module functions — the tests patch only ``get_by_slug``
and the device cache, so the fakes must expose the same attributes those module
functions read and write (``cc.media_controller``, ``cc.status.volume_level``,
``device.volume``, ``device.play_mode``, …). Each fake also records the calls
made against it so tests can assert on side effects.
"""


class _MediaControllerStatus:
    def __init__(self):
        self.player_state = "UNKNOWN"
        self.idle_reason = None
        self.content_id = None
        self.title = None
        self.media_metadata = {}

    @property
    def player_is_paused(self):
        return self.player_state == "PAUSED"

    @property
    def player_is_playing(self):
        return self.player_state in ("PLAYING", "BUFFERING")


class _FakeMediaController:
    def __init__(self, owner):
        self._owner = owner
        self.status = _MediaControllerStatus()

    def play_media(self, url, media_type):
        self._owner.calls.append(("play_media", url, media_type))
        self.status.player_state = "PLAYING"
        self.status.content_id = url

    def block_until_active(self):
        pass

    def pause(self):
        self._owner.calls.append(("pause",))
        self.status.player_state = "PAUSED"

    def play(self):
        self._owner.calls.append(("play",))
        self.status.player_state = "PLAYING"

    def register_status_listener(self, listener):
        pass


class FakeChromecast:
    """Stand-in for a pychromecast Chromecast object."""

    def __init__(self, volume=0.5, player_state="IDLE"):
        self.calls = []
        self.media_controller = _FakeMediaController(self)
        self.media_controller.status.player_state = player_state
        # cc.status is the receiver status; volume_level lives here.
        self.status = _MediaControllerStatus()
        self.status.volume_level = volume

    def set_volume(self, volume):
        self.calls.append(("set_volume", volume))
        self.status.volume_level = float(volume)

    def quit_app(self):
        self.calls.append(("quit_app",))
        self.media_controller.status.player_state = "IDLE"


class FakeSonos:
    """Stand-in for a SoCo device object."""

    def __init__(self, volume=50, transport_state="STOPPED", play_mode="NORMAL"):
        self.calls = []
        self.volume = volume
        self._transport_state = transport_state
        self.play_mode = play_mode

    def play_uri(self, uri, force_radio=False):
        self.calls.append(("play_uri", uri, force_radio))
        self._transport_state = "PLAYING"

    def pause(self):
        self.calls.append(("pause",))
        self._transport_state = "PAUSED_PLAYBACK"

    def play(self):
        self.calls.append(("play",))
        self._transport_state = "PLAYING"

    def stop(self):
        self.calls.append(("stop",))
        self._transport_state = "STOPPED"

    def next(self):
        self.calls.append(("next",))

    def previous(self):
        self.calls.append(("previous",))

    def set_relative_volume(self, delta):
        self.calls.append(("set_relative_volume", delta))
        self.volume = max(0, min(100, self.volume + delta))

    def get_current_transport_info(self):
        return {"current_transport_state": self._transport_state}

    def get_current_track_info(self):
        return {"uri": "x-rincon:current"}


class DeviceRegistry:
    """Holds fakes and answers get_by_slug / get_all_devices like the real modules."""

    def __init__(self):
        self._chromecasts = {}  # slug -> FakeChromecast
        self._sonos = {}        # slug -> FakeSonos

    def add_chromecast(self, slug, **kwargs):
        cc = FakeChromecast(**kwargs)
        self._chromecasts[slug] = cc
        return cc

    def add_sonos(self, slug, **kwargs):
        device = FakeSonos(**kwargs)
        self._sonos[slug] = device
        return device

    def get_chromecast(self, slug):
        return self._chromecasts.get(slug)

    def get_sonos(self, slug):
        return self._sonos.get(slug)

    def get_all_devices(self):
        devices = [{"slug": s, "type": "chromecast"} for s in self._chromecasts]
        devices += [{"slug": s, "type": "sonos"} for s in self._sonos]
        return devices
