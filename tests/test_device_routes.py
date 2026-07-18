"""Tests for the slug-based device control endpoints (app/devices/routes.py).

Devices are faked (tests/fakes.py); the real chromecast/sonos module functions
run against them, so these tests exercise the routing, fan-out, volume-lock and
sleep-timer logic end to end without any hardware.
"""


# --- Basic playback actions: chromecast ---

def test_pause_chromecast(client, registry):
    cc = registry.add_chromecast("kitchen", player_state="PLAYING")
    resp = client.post("/device/slug/pause", json={"slug": "kitchen", "type": "chromecast"})
    assert resp.status_code == 200
    assert resp.get_json() == {"status": "paused"}
    assert ("pause",) in cc.calls


def test_resume_chromecast(client, registry):
    cc = registry.add_chromecast("kitchen", player_state="PAUSED")
    resp = client.post("/device/slug/resume", json={"slug": "kitchen", "type": "chromecast"})
    assert resp.status_code == 200
    assert resp.get_json() == {"status": "playing"}
    assert ("play",) in cc.calls


def test_stop_chromecast(client, registry):
    cc = registry.add_chromecast("kitchen", player_state="PLAYING")
    resp = client.post("/device/slug/stop", json={"slug": "kitchen", "type": "chromecast"})
    assert resp.status_code == 200
    assert resp.get_json() == {"status": "stopped"}
    assert ("quit_app",) in cc.calls


def test_play_url_chromecast(client, registry):
    cc = registry.add_chromecast("kitchen")
    resp = client.post("/device/slug/play-url", json={
        "slug": "kitchen", "type": "chromecast",
        "url": "http://example.com/song.mp3",
    })
    assert resp.status_code == 200
    assert resp.get_json() == {"status": "playing", "url": "http://example.com/song.mp3"}
    assert ("play_media", "http://example.com/song.mp3", "audio/mp3") in cc.calls


def test_default_type_is_chromecast(client, registry):
    """Omitting 'type' should resolve to a chromecast."""
    cc = registry.add_chromecast("kitchen", player_state="PLAYING")
    resp = client.post("/device/slug/pause", json={"slug": "kitchen"})
    assert resp.status_code == 200
    assert ("pause",) in cc.calls


# --- Basic playback actions: sonos ---

def test_pause_sonos(client, registry):
    device = registry.add_sonos("living_room", transport_state="PLAYING")
    resp = client.post("/device/slug/pause", json={"slug": "living_room", "type": "sonos"})
    assert resp.status_code == 200
    assert resp.get_json() == {"status": "paused"}
    assert ("pause",) in device.calls


def test_play_url_sonos_uses_force_radio(client, registry):
    device = registry.add_sonos("living_room")
    resp = client.post("/device/slug/play-url", json={
        "slug": "living_room", "type": "sonos",
        "url": "http://example.com/stream",
    })
    assert resp.status_code == 200
    assert ("play_uri", "http://example.com/stream", True) in device.calls


def test_next_prev_sonos(client, registry):
    device = registry.add_sonos("living_room")
    r1 = client.post("/device/slug/next", json={"slug": "living_room", "type": "sonos"})
    r2 = client.post("/device/slug/prev", json={"slug": "living_room", "type": "sonos"})
    assert r1.get_json() == {"status": "next"}
    assert r2.get_json() == {"status": "previous"}
    assert ("next",) in device.calls
    assert ("previous",) in device.calls


def test_next_prev_chromecast_foreign_app_when_supported(client, registry):
    # No home-cast queue: skip is delegated to the running cast app (e.g. the
    # official YouTube Music receiver) over the media namespace.
    cc = registry.add_chromecast("kitchen", player_state="PLAYING")
    cc.media_controller.status.supports_queue_next = True
    cc.media_controller.status.supports_queue_prev = True

    r1 = client.post("/device/slug/next", json={"slug": "kitchen", "type": "chromecast"})
    r2 = client.post("/device/slug/prev", json={"slug": "kitchen", "type": "chromecast"})

    assert r1.get_json() == {"status": "next"}
    assert r2.get_json() == {"status": "previous"}
    assert ("queue_next",) in cc.calls
    assert ("queue_prev",) in cc.calls


def test_next_chromecast_foreign_app_unsupported(client, registry):
    # Radio and other queue-less media don't advertise skip support: refuse
    # rather than send a no-op skip.
    cc = registry.add_chromecast("kitchen", player_state="PLAYING")
    cc.media_controller.status.supports_queue_next = False

    resp = client.post("/device/slug/next", json={"slug": "kitchen", "type": "chromecast"})

    assert resp.status_code == 400
    assert ("queue_next",) not in cc.calls


# --- Cast queue metadata ---

def test_build_metadata_strips_base64_cover(registry):
    # A base64 data: URI cover must NOT be sent to the receiver — embedding a
    # large image on every queue item overflows the Cast custom-message size
    # limit and breaks the socket. A real URL is passed through.
    from app.devices.chromecast import CustomReceiverQueue

    cc = registry.add_chromecast("kitchen")
    q = CustomReceiverQueue(cc, cache=None, cast_app_id=None)

    data_meta = q._build_metadata({"title": "A", "thumbnail": "data:image/jpeg;base64,ABCD"})
    assert data_meta["images"] == []

    url_meta = q._build_metadata({"title": "B", "thumbnail": "http://img/b.jpg"})
    assert url_meta["images"] == [{"url": "http://img/b.jpg"}]


# --- Device-not-found handling ---

def test_pause_unknown_device_404_style(client, registry):
    resp = client.post("/device/slug/pause", json={"slug": "nope", "type": "chromecast"})
    assert resp.status_code == 400
    assert resp.get_json() == {"error": "Device not found"}


def test_play_url_unknown_device(client, registry):
    resp = client.post("/device/slug/play-url", json={"slug": "nope", "url": "x"})
    assert resp.status_code == 400
    assert resp.get_json() == {"error": "Device not found"}


def test_next_unknown_sonos_device(client, registry):
    resp = client.post("/device/slug/next", json={"slug": "nope", "type": "sonos"})
    assert resp.status_code == 400
    assert resp.get_json() == {"error": "Device not found"}


# --- Volume ---

def test_get_volume_chromecast(client, registry):
    registry.add_chromecast("kitchen", volume=0.4)
    resp = client.post("/device/slug/volume", json={"slug": "kitchen", "type": "chromecast"})
    assert resp.get_json() == {"volume": 0.4}


def test_get_volume_sonos_scales_to_fraction(client, registry):
    registry.add_sonos("living_room", volume=75)
    resp = client.post("/device/slug/volume", json={"slug": "living_room", "type": "sonos"})
    assert resp.get_json() == {"volume": 0.75}


def test_set_volume_chromecast(client, registry):
    cc = registry.add_chromecast("kitchen", volume=0.2)
    resp = client.post("/device/slug/volume/set", json={
        "slug": "kitchen", "type": "chromecast", "volume": 0.8,
    })
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["volume"] == 0.8
    assert cc.status.volume_level == 0.8


def test_volume_delta_clamps_at_one(client, registry):
    cc = registry.add_chromecast("kitchen", volume=0.9)
    resp = client.post("/device/slug/volume/delta", json={
        "slug": "kitchen", "type": "chromecast", "delta": 0.5,
    })
    assert resp.status_code == 200
    assert cc.status.volume_level == 1.0


def test_volume_delta_clamps_at_zero(client, registry):
    cc = registry.add_chromecast("kitchen", volume=0.1)
    resp = client.post("/device/slug/volume/delta", json={
        "slug": "kitchen", "type": "chromecast", "delta": -0.5,
    })
    assert resp.status_code == 200
    assert cc.status.volume_level == 0.0
