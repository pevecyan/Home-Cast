import json
import logging
from pathlib import Path

from flask import Flask, request, jsonify

from app.config import load_config
from app.devices.discovery import start_cache_updater
from app.devices.routes import devices_bp
from app.music.routes import music_bp
from app.music.downloader import init_cache
from app.media.routes import media_bp
from app.radio.routes import radio_bp
from app.storage_routes import storage_bp
from app.ws import socketio, start_poll_thread

logger = logging.getLogger(__name__)


def create_app(config_path="config.yaml"):
    config = load_config(config_path)

    flask_app = Flask(__name__)
    flask_app.config["APP"] = config
    flask_app.config["SECRET_KEY"] = "home-cast-ws"

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    _changelog_path = Path(__file__).parent.parent / "CHANGELOG.json"

    @flask_app.route("/version")
    def version():
        try:
            changelog = json.loads(_changelog_path.read_text())
        except Exception:
            changelog = []
        current = changelog[0]["version"] if changelog else "0.0.0"
        return jsonify({"version": current, "changelog": changelog})

    @flask_app.before_request
    def log_request():
        logger.info("%s %s", request.method, request.url)

    init_cache(config)

    flask_app.register_blueprint(devices_bp)
    flask_app.register_blueprint(music_bp)
    flask_app.register_blueprint(media_bp)
    flask_app.register_blueprint(radio_bp)
    flask_app.register_blueprint(storage_bp)

    socketio.init_app(flask_app)

    start_cache_updater()
    start_poll_thread()

    return flask_app
