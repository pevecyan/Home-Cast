from flask import Blueprint, request, jsonify
from app import storage

storage_bp = Blueprint("storage", __name__, url_prefix="/storage")


# --- Favorite radios ---

@storage_bp.route("/favorites", methods=["GET"])
def list_favorites():
    return jsonify(storage.get_favorites())


@storage_bp.route("/favorites", methods=["POST"])
def add_favorite():
    station = request.json
    return jsonify(storage.add_favorite(station))


@storage_bp.route("/favorites/<stationuuid>", methods=["DELETE"])
def remove_favorite(stationuuid):
    return jsonify(storage.remove_favorite(stationuuid))


# --- Settings ---

@storage_bp.route("/settings", methods=["GET"])
def get_settings():
    return jsonify(storage.get_settings())


@storage_bp.route("/settings", methods=["POST"])
def save_settings():
    return jsonify(storage.save_settings(request.json))


# --- Recents ---

@storage_bp.route("/recents", methods=["GET"])
def list_recents():
    return jsonify(storage.get_recents())


@storage_bp.route("/recents", methods=["POST"])
def add_recent():
    item = request.json
    return jsonify(storage.add_recent(item))
