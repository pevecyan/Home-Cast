"""Alarm scheduling — storage CRUD, REST endpoints, and the fire engine.

The scheduler fires from a background thread with no request context, so these
tests exercise ``_check_due`` / ``_fire`` directly (deterministic, no sleeping
on the minute tick) and stub the play helpers to record what would have played.
"""

import json
from datetime import datetime

import pytest
from flask import Flask

from app import storage
from app.schedule import routes as sched_routes
from app.schedule import scheduler
from app.music import player


@pytest.fixture
def data_dir(tmp_path, monkeypatch):
    """Point every storage file at a fresh temp dir so tests don't touch data/."""
    monkeypatch.setattr(storage, "DATA_DIR", tmp_path)
    monkeypatch.setattr(storage, "ALARMS_FILE", tmp_path / "alarms.json")
    monkeypatch.setattr(storage, "FAVORITES_FILE", tmp_path / "favorite_radios.json")
    monkeypatch.setattr(storage, "SETTINGS_FILE", tmp_path / "settings.json")
    monkeypatch.setattr(storage, "RECENTS_FILE", tmp_path / "recents.json")
    return tmp_path


@pytest.fixture
def app(data_dir):
    flask_app = Flask(__name__)
    flask_app.config["TESTING"] = True
    flask_app.config["APP"] = {"hostname": "http://test:5000", "cast_app_id": None}
    flask_app.register_blueprint(sched_routes.schedule_bp)
    return flask_app


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture(autouse=True)
def _reset_fired():
    scheduler._last_fired.clear()
    yield
    scheduler._last_fired.clear()


# --- REST endpoints ---

def test_create_list_get_update_delete(client):
    resp = client.post("/schedule/alarms", json={
        "time": "07:30", "days": [0, 1, 2],
        "action": {"kind": "playlist", "ref": "pl1", "name": "Wake"},
        "shuffle": True, "repeat": "all",
    })
    assert resp.status_code == 201
    alarm = resp.get_json()
    aid = alarm["id"]
    assert alarm["time"] == "07:30"
    assert alarm["shuffle"] is True
    assert alarm["repeat"] == "all"

    listed = client.get("/schedule/alarms").get_json()
    assert len(listed) == 1 and listed[0]["id"] == aid

    got = client.get(f"/schedule/alarms/{aid}")
    assert got.status_code == 200 and got.get_json()["time"] == "07:30"

    updated = client.put(f"/schedule/alarms/{aid}", json={"time": "08:00"}).get_json()
    assert updated["time"] == "08:00"
    assert updated["days"] == [0, 1, 2]  # untouched fields preserved

    assert client.delete(f"/schedule/alarms/{aid}").status_code == 200
    assert client.get("/schedule/alarms").get_json() == []


def test_get_missing_alarm_404(client):
    assert client.get("/schedule/alarms/nope").status_code == 404
    assert client.put("/schedule/alarms/nope", json={"time": "09:00"}).status_code == 404


def test_toggle_flips_and_respects_explicit(client):
    aid = client.post("/schedule/alarms", json={"time": "07:00"}).get_json()["id"]
    # default enabled=True -> flip to False
    assert client.post(f"/schedule/alarms/{aid}/toggle").get_json()["enabled"] is False
    # flip back
    assert client.post(f"/schedule/alarms/{aid}/toggle").get_json()["enabled"] is True
    # explicit
    assert client.post(f"/schedule/alarms/{aid}/toggle", json={"enabled": False}).get_json()["enabled"] is False


def test_alarm_survives_reload(client, data_dir):
    aid = client.post("/schedule/alarms", json={"time": "06:15", "days": [5, 6]}).get_json()["id"]
    # Simulate a restart: read the persisted file straight from disk.
    on_disk = json.loads((data_dir / "alarms.json").read_text())
    assert len(on_disk) == 1
    assert on_disk[0]["id"] == aid and on_disk[0]["time"] == "06:15"


# --- Fire engine ---

def _due(dt):
    return dt


def test_check_due_matches_time_and_weekday(app, monkeypatch):
    fired = []
    monkeypatch.setattr(scheduler, "_fire", lambda a: fired.append(a["id"]))

    a1 = storage.add_alarm({"time": "07:30", "days": [0, 1]})   # Mon/Tue
    storage.add_alarm({"time": "07:30", "days": [3]})           # Thu only
    storage.add_alarm({"time": "07:30", "days": [], "enabled": False})  # disabled
    storage.add_alarm({"time": "09:00", "days": []})           # wrong time
    oneshot = storage.add_alarm({"time": "07:30", "days": []})

    mon_0730 = datetime(2026, 7, 13, 7, 30, 5)  # Monday
    scheduler._check_due(mon_0730)
    assert set(fired) == {a1["id"], oneshot["id"]}


def test_check_due_no_double_fire_same_minute(app, monkeypatch):
    fired = []
    monkeypatch.setattr(scheduler, "_fire", lambda a: fired.append(a["id"]))
    storage.add_alarm({"time": "07:30", "days": []})
    dt = datetime(2026, 7, 13, 7, 30, 5)
    scheduler._check_due(dt)
    scheduler._check_due(dt)
    assert len(fired) == 1


def test_fire_playlist_plays_on_all_targets(app, monkeypatch):
    calls = []
    monkeypatch.setattr(scheduler, "_app", app)
    monkeypatch.setattr(scheduler, "broadcast_states", lambda: None)
    monkeypatch.setattr(scheduler, "_resolve_targets",
                        lambda slug, dtype: [("kitchen", "chromecast"), ("lr", "sonos")])
    monkeypatch.setattr(player, "play_saved_playlist",
                        lambda cfg, ref, slug, dtype, **kw: calls.append((ref, slug, dtype, kw)))

    alarm = storage.add_alarm({
        "time": "07:30", "days": [],
        "target": {"slug": "all", "type": "all"},
        "action": {"kind": "playlist", "ref": "pl1"},
        "shuffle": True, "repeat": "all",
    })
    scheduler._fire(alarm)

    assert len(calls) == 2
    assert {c[1] for c in calls} == {"kitchen", "lr"}
    assert all(c[3]["shuffle"] is True and c[3]["repeat"] == "all" for c in calls)


def test_fire_oneshot_disables_itself(app, monkeypatch):
    monkeypatch.setattr(scheduler, "_app", app)
    monkeypatch.setattr(scheduler, "broadcast_states", lambda: None)
    monkeypatch.setattr(scheduler, "_resolve_targets", lambda s, t: [("kitchen", "chromecast")])
    monkeypatch.setattr(player, "play_saved_playlist", lambda *a, **k: None)

    alarm = storage.add_alarm({
        "time": "07:30", "days": [],
        "action": {"kind": "playlist", "ref": "pl1"},
    })
    scheduler._fire(alarm)
    assert storage.get_alarms()[0]["enabled"] is False


def test_fire_recurring_stays_enabled(app, monkeypatch):
    monkeypatch.setattr(scheduler, "_app", app)
    monkeypatch.setattr(scheduler, "broadcast_states", lambda: None)
    monkeypatch.setattr(scheduler, "_resolve_targets", lambda s, t: [("kitchen", "chromecast")])
    monkeypatch.setattr(player, "play_saved_playlist", lambda *a, **k: None)

    alarm = storage.add_alarm({
        "time": "07:30", "days": [0, 1, 2],
        "action": {"kind": "playlist", "ref": "pl1"},
    })
    scheduler._fire(alarm)
    assert storage.get_alarms()[0]["enabled"] is True


def test_fire_radio_resolves_favorite(app, monkeypatch):
    played = []
    monkeypatch.setattr(scheduler, "_app", app)
    monkeypatch.setattr(scheduler, "broadcast_states", lambda: None)
    monkeypatch.setattr(scheduler, "_resolve_targets", lambda s, t: [("kitchen", "chromecast")])
    monkeypatch.setattr(player, "play_radio",
                        lambda slug, dtype, url, **kw: played.append((slug, url, kw)))

    storage.add_favorite({"stationuuid": "st1", "name": "Jazz FM", "url": "http://x/stream", "favicon": None})
    alarm = storage.add_alarm({
        "time": "07:30", "days": [],
        "action": {"kind": "radio", "ref": "st1"},
    })
    scheduler._fire(alarm)
    assert len(played) == 1
    assert played[0][1] == "http://x/stream"
    assert played[0][2]["station_name"] == "Jazz FM"


def test_fire_volume_and_fade(app, monkeypatch):
    vol_calls = []
    monkeypatch.setattr(scheduler, "_app", app)
    monkeypatch.setattr(scheduler, "broadcast_states", lambda: None)
    monkeypatch.setattr(scheduler, "_resolve_targets", lambda s, t: [("kitchen", "chromecast")])
    monkeypatch.setattr(player, "play_saved_playlist", lambda *a, **k: None)
    monkeypatch.setattr(scheduler, "_set_volume",
                        lambda slug, dtype, vol: vol_calls.append(vol))
    # Don't actually spawn the fade thread (it sleeps); just confirm it starts near-silent.
    started = {}
    monkeypatch.setattr(scheduler.threading, "Thread",
                        lambda target, args, daemon: type("T", (), {"start": lambda self: started.update(args=args)})())

    alarm = storage.add_alarm({
        "time": "07:30", "days": [],
        "action": {"kind": "playlist", "ref": "pl1"},
        "volume": 0.6, "fadeIn": 30,
    })
    scheduler._fire(alarm)
    # With fade-in the starting volume is near-silent, not the target.
    assert vol_calls == [0.05]
    # The fade thread would ramp 0.05 -> 0.6.
    assert started["args"][1] == 0.05 and started["args"][2] == 0.6
