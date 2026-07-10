"""Shared test fixtures.

The device-control routes talk to physical Chromecast/Sonos devices through the
``app.devices.chromecast`` and ``app.devices.sonos`` modules. Tests never touch
real hardware: we register only the ``devices_bp`` blueprint on a bare Flask app,
stub out ``broadcast_states`` (no websockets), and swap in fake device objects
through a small in-memory registry (see :mod:`tests.fakes`).
"""

import pytest
from flask import Flask

from app.devices import routes as routes_mod
from app.devices import chromecast, sonos
from app.devices import discovery

from tests.fakes import FakeChromecast, FakeSonos, DeviceRegistry


@pytest.fixture
def registry(monkeypatch):
    """An in-memory device registry wired into the chromecast/sonos modules.

    Add fakes with ``registry.add_chromecast(...)`` / ``registry.add_sonos(...)``;
    lookups via ``chromecast.get_by_slug`` / ``sonos.get_by_slug`` and the
    ``get_all_devices`` fan-out source then resolve to those fakes.
    """
    reg = DeviceRegistry()

    monkeypatch.setattr(chromecast, "get_by_slug", reg.get_chromecast)
    monkeypatch.setattr(sonos, "get_by_slug", reg.get_sonos)
    # routes.py imported these names directly, so patch them there too.
    monkeypatch.setattr(routes_mod.chromecast, "get_by_slug", reg.get_chromecast)
    monkeypatch.setattr(routes_mod.sonos, "get_by_slug", reg.get_sonos)
    # Fan-out ("all") resolves targets through discovery.get_all_devices.
    monkeypatch.setattr(routes_mod, "get_all_devices", reg.get_all_devices)
    monkeypatch.setattr(discovery, "get_all_devices", reg.get_all_devices)

    return reg


@pytest.fixture
def app(registry, monkeypatch):
    """Bare Flask app with just the devices blueprint and no websockets/threads."""
    # broadcast_states is imported into routes at module load; stub it to a no-op
    # so route handlers don't try to reach the websocket/poll machinery.
    monkeypatch.setattr(routes_mod, "broadcast_states", lambda: None)

    flask_app = Flask(__name__)
    flask_app.config["TESTING"] = True
    flask_app.register_blueprint(routes_mod.devices_bp)
    return flask_app


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture(autouse=True)
def _reset_route_module_state():
    """Keep module-level dicts (locks, timers, queues) isolated between tests."""
    routes_mod._volume_locks.clear()
    routes_mod._sleep_timers.clear()
    chromecast._queues.clear()
    yield
    for info in routes_mod._sleep_timers.values():
        try:
            info["timer"].cancel()
        except Exception:
            pass
    routes_mod._volume_locks.clear()
    routes_mod._sleep_timers.clear()
    chromecast._queues.clear()
