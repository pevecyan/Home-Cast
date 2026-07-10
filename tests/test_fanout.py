"""Fan-out behavior for slug=='all' — the aggregate-response path in _fan_out."""


def _results_by_slug(body):
    return {r["slug"]: r for r in body["results"]}


def test_pause_all_hits_every_device(client, registry):
    k = registry.add_chromecast("kitchen", player_state="PLAYING")
    b = registry.add_chromecast("bedroom", player_state="PLAYING")
    s = registry.add_sonos("living_room", transport_state="PLAYING")

    resp = client.post("/device/slug/pause", json={"slug": "all"})
    assert resp.status_code == 200
    by_slug = _results_by_slug(resp.get_json())
    assert set(by_slug) == {"kitchen", "bedroom", "living_room"}
    assert all(r["ok"] for r in by_slug.values())
    assert ("pause",) in k.calls
    assert ("pause",) in b.calls
    assert ("pause",) in s.calls


def test_all_filters_by_type(client, registry):
    registry.add_chromecast("kitchen", player_state="PLAYING")
    registry.add_sonos("living_room", transport_state="PLAYING")

    resp = client.post("/device/slug/pause", json={"slug": "all", "type": "sonos"})
    by_slug = _results_by_slug(resp.get_json())
    assert set(by_slug) == {"living_room"}


def test_all_tolerates_per_device_failure(client, registry):
    """One failing device must not abort the rest; it comes back ok:false."""
    good = registry.add_chromecast("kitchen", player_state="PLAYING")
    bad = registry.add_chromecast("bedroom", player_state="PLAYING")

    def boom():
        raise RuntimeError("device offline")
    bad.quit_app = boom  # stop() calls quit_app under the hood

    resp = client.post("/device/slug/stop", json={"slug": "all"})
    assert resp.status_code == 200
    by_slug = _results_by_slug(resp.get_json())
    assert by_slug["kitchen"]["ok"] is True
    assert by_slug["bedroom"]["ok"] is False
    assert "device offline" in by_slug["bedroom"]["error"]
    assert ("quit_app",) in good.calls


def test_set_volume_all_skips_locked_device(client, registry):
    """In an all-fanout a locked device is an ok:false entry, others still change."""
    free = registry.add_chromecast("kitchen", volume=0.2)
    locked = registry.add_chromecast("bedroom", volume=0.5)
    client.post("/device/slug/volume/lock", json={"slug": "bedroom", "type": "chromecast"})

    resp = client.post("/device/slug/volume/set", json={"slug": "all", "volume": 0.9})
    assert resp.status_code == 200
    by_slug = _results_by_slug(resp.get_json())
    assert by_slug["kitchen"]["ok"] is True
    assert by_slug["bedroom"]["ok"] is False
    assert "locked" in by_slug["bedroom"]["error"]
    assert free.status.volume_level == 0.9
    assert locked.status.volume_level == 0.5  # unchanged


def test_all_with_no_devices_returns_empty_results(client, registry):
    resp = client.post("/device/slug/pause", json={"slug": "all"})
    assert resp.status_code == 200
    assert resp.get_json() == {"results": []}
