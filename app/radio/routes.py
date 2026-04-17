import logging

import requests
from flask import Blueprint, request, jsonify

from app.devices import chromecast, sonos

logger = logging.getLogger(__name__)

radio_bp = Blueprint("radio", __name__, url_prefix="/radio")

API_BASE = "https://de1.api.radio-browser.info/json"
DEFAULT_COUNTRY = "Slovenia"


def _fetch_stations(params):
    resp = requests.get(
        f"{API_BASE}/stations/search",
        params=params,
        headers={"User-Agent": "home-cast/1.0"},
        timeout=10,
    )
    resp.raise_for_status()
    stations = resp.json()
    return [
        {
            "stationuuid": s["stationuuid"],
            "name": s["name"],
            "url": s.get("url_resolved") or s["url"],
            "favicon": s.get("favicon") or None,
            "tags": s.get("tags", ""),
            "codec": s.get("codec", ""),
            "bitrate": s.get("bitrate", 0),
            "votes": s.get("votes", 0),
        }
        for s in stations
        if s.get("url_resolved") or s.get("url")
    ]


@radio_bp.route("/search", methods=["GET"])
def search_stations():
    query = request.args.get("q", "")
    if not query:
        # No query — return popular Slovenian stations
        params = {
            "country": DEFAULT_COUNTRY,
            "limit": 30,
            "order": "votes",
            "reverse": "true",
            "hidebroken": "true",
        }
        return jsonify(_fetch_stations(params))

    params = {
        "country": DEFAULT_COUNTRY,
        "name": query,
        "limit": 50,
        "order": "votes",
        "reverse": "true",
        "hidebroken": "true",
    }
    return jsonify(_fetch_stations(params))


@radio_bp.route("/popular", methods=["GET"])
def popular_stations():
    params = {
        "country": DEFAULT_COUNTRY,
        "limit": 30,
        "order": "votes",
        "reverse": "true",
        "hidebroken": "true",
    }
    stations = _fetch_stations(params)
    return jsonify(stations)


@radio_bp.route("/play", methods=["POST"])
def play_station():
    data = request.json
    slug = data.get("slug")
    device_type = data.get("type", "chromecast")
    station_url = data.get("stationUrl")
    station_name = data.get("stationName", "Radio")
    station_favicon = data.get("stationFavicon")

    if not slug or not station_url:
        return jsonify({"error": "Missing slug or stationUrl"}), 400

    if device_type == "sonos":
        device = sonos.get_by_slug(slug)
        if not device:
            return jsonify({"error": "Sonos device not found"}), 400
        sonos.play_media(device, station_url)
    else:
        cc = chromecast.get_by_slug(slug)
        if not cc:
            return jsonify({"error": "Chromecast device not found"}), 400

        metadata = {
            "metadataType": 0,
            "title": station_name,
            "images": [{"url": station_favicon}] if station_favicon else [],
        }
        cc.media_controller.play_media(
            station_url,
            "audio/mpeg",
            title=station_name,
            thumb=station_favicon,
            metadata=metadata,
            stream_type="LIVE",
        )
        cc.media_controller.block_until_active()

    return jsonify({"status": "playing", "station": station_name})
