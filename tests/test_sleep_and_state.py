"""Sleep-timer scheduling and device-state endpoints."""

import threading

import pytest

from app.devices import routes as routes_mod


class _ImmediateTimer:
    """A threading.Timer stand-in that never actually fires on its own.

    Records that it was created/started/cancelled so tests can assert on the
    bookkeeping without waiting real wall-clock minutes. ``fire()`` invokes the
    callback synchronously to simulate expiry.
    """

    instances = []

    def __init__(self, interval, function, args=None, kwargs=None):
        self.interval = interval
        self.function = function
        self.args = args or []
        self.kwargs = kwargs or {}
        self.daemon = False
        self._alive = False
        _ImmediateTimer.instances.append(self)

    def start(self):
        self._alive = True

    def cancel(self):
        self._alive = False

    def is_alive(self):
        return self._alive

    def fire(self):
        self._alive = False
        self.function(*self.args, **self.kwargs)


@pytest.fixture
def fake_timer(monkeypatch):
    _ImmediateTimer.instances = []
    monkeypatch.setattr(routes_mod.threading, "Timer", _ImmediateTimer)
    return _ImmediateTimer


def test_sleep_schedules_timer(client, registry, fake_timer):
    registry.add_chromecast("kitchen", player_state="PLAYING")
    resp = client.post("/device/slug/sleep", json={
        "slug": "kitchen", "type": "chromecast", "minutes": 30,
    })
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["sleepMinutes"] == 30
    assert body["sleepEndsAt"] is not None
    assert len(fake_timer.instances) == 1
    assert fake_timer.instances[0].interval == 30 * 60
    assert fake_timer.instances[0].is_alive()


def test_sleep_zero_cancels(client, registry, fake_timer):
    registry.add_chromecast("kitchen", player_state="PLAYING")
    client.post("/device/slug/sleep", json={"slug": "kitchen", "type": "chromecast", "minutes": 15})
    resp = client.post("/device/slug/sleep", json={"slug": "kitchen", "type": "chromecast", "minutes": 0})
    assert resp.status_code == 200
    assert resp.get_json() == {"status": "cancelled"}
    # original timer was cancelled
    assert not fake_timer.instances[0].is_alive()


def test_rescheduling_cancels_previous(client, registry, fake_timer):
    registry.add_chromecast("kitchen", player_state="PLAYING")
    client.post("/device/slug/sleep", json={"slug": "kitchen", "type": "chromecast", "minutes": 15})
    client.post("/device/slug/sleep", json={"slug": "kitchen", "type": "chromecast", "minutes": 45})
    assert len(fake_timer.instances) == 2
    assert not fake_timer.instances[0].is_alive()  # first cancelled
    assert fake_timer.instances[1].is_alive()      # second active


def test_sleep_timer_expiry_stops_device(client, registry, fake_timer):
    cc = registry.add_chromecast("kitchen", player_state="PLAYING")
    client.post("/device/slug/sleep", json={"slug": "kitchen", "type": "chromecast", "minutes": 5})
    fake_timer.instances[0].fire()
    assert ("quit_app",) in cc.calls
    # timer entry cleaned up after firing
    assert "kitchen:chromecast" not in routes_mod._sleep_timers


def test_state_includes_active_sleep_timer(client, registry, fake_timer):
    registry.add_chromecast("kitchen", player_state="PLAYING")
    client.post("/device/slug/sleep", json={"slug": "kitchen", "type": "chromecast", "minutes": 20})
    resp = client.post("/device/slug/state", json={"slug": "kitchen", "type": "chromecast"})
    body = resp.get_json()
    assert "sleepTimer" in body
    assert "endsAt" in body["sleepTimer"]


# --- State ---

def test_state_chromecast_playing(client, registry):
    cc = registry.add_chromecast("kitchen", volume=0.6, player_state="PLAYING")
    cc.media_controller.status.title = "Song A"
    cc.media_controller.status.content_id = "abc"
    resp = client.post("/device/slug/state", json={"slug": "kitchen", "type": "chromecast"})
    body = resp.get_json()
    assert body["status"] == "PLAYING"
    assert body["volume"] == 0.6
    assert body["nowPlaying"]["title"] == "Song A"


def test_state_chromecast_idle_has_no_now_playing(client, registry):
    registry.add_chromecast("kitchen", volume=0.6, player_state="IDLE")
    resp = client.post("/device/slug/state", json={"slug": "kitchen", "type": "chromecast"})
    body = resp.get_json()
    assert body["status"] == "IDLE"
    assert "nowPlaying" not in body


def test_state_sonos(client, registry):
    registry.add_sonos("living_room", volume=30, transport_state="PAUSED_PLAYBACK")
    resp = client.post("/device/slug/state", json={"slug": "living_room", "type": "sonos"})
    body = resp.get_json()
    assert body["status"] == "PAUSED"
    assert body["volume"] == 0.3


def test_state_unknown_device(client, registry):
    resp = client.post("/device/slug/state", json={"slug": "nope", "type": "chromecast"})
    assert resp.status_code == 400
