"""Volume-lock behavior for /device/slug/volume/{set,delta,lock,unlock}."""


def test_lock_snapshots_current_volume(client, registry):
    cc = registry.add_chromecast("kitchen", volume=0.35)
    resp = client.post("/device/slug/volume/lock", json={"slug": "kitchen", "type": "chromecast"})
    assert resp.status_code == 200
    assert resp.get_json() == {"locked": True, "volume": 0.35}


def test_set_volume_blocked_when_locked(client, registry):
    registry.add_chromecast("kitchen", volume=0.35)
    client.post("/device/slug/volume/lock", json={"slug": "kitchen", "type": "chromecast"})
    resp = client.post("/device/slug/volume/set", json={
        "slug": "kitchen", "type": "chromecast", "volume": 0.9,
    })
    assert resp.status_code == 423
    assert resp.get_json() == {"error": "volume locked"}


def test_delta_blocked_when_locked(client, registry):
    registry.add_chromecast("kitchen", volume=0.35)
    client.post("/device/slug/volume/lock", json={"slug": "kitchen", "type": "chromecast"})
    resp = client.post("/device/slug/volume/delta", json={
        "slug": "kitchen", "type": "chromecast", "delta": 0.1,
    })
    assert resp.status_code == 423


def test_unlock_allows_set_again(client, registry):
    cc = registry.add_chromecast("kitchen", volume=0.35)
    client.post("/device/slug/volume/lock", json={"slug": "kitchen", "type": "chromecast"})
    client.post("/device/slug/volume/unlock", json={"slug": "kitchen", "type": "chromecast"})
    resp = client.post("/device/slug/volume/set", json={
        "slug": "kitchen", "type": "chromecast", "volume": 0.9,
    })
    assert resp.status_code == 200
    assert cc.status.volume_level == 0.9


def test_lock_is_per_device_type(client, registry):
    """A lock on kitchen:chromecast must not block a sonos with the same slug."""
    registry.add_chromecast("kitchen", volume=0.35)
    registry.add_sonos("kitchen", volume=40)
    client.post("/device/slug/volume/lock", json={"slug": "kitchen", "type": "chromecast"})
    resp = client.post("/device/slug/volume/set", json={
        "slug": "kitchen", "type": "sonos", "volume": 0.9,
    })
    assert resp.status_code == 200


def test_lock_unknown_device(client, registry):
    resp = client.post("/device/slug/volume/lock", json={"slug": "nope", "type": "chromecast"})
    assert resp.status_code == 400
